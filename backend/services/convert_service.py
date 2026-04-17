"""
쿼리 변환 오케스트레이션 서비스
LLM 변환 → Dry-run → Difficulty 분류의 전체 파이프라인
"""
import logging
import json
import time
from typing import Optional

import psycopg2

from backend.schemas.project import DBConfig
from backend.schemas.convert import (
    ConvertRequest,
    ConvertResponse,
    QueryResult,
    ConversionLogEntry,
    DryRunResult,
)
from backend.services import project_service
from backend.services import llm_client
from backend.services import schema_fetcher
from backend.services import dryrun_service
from backend.services.difficulty_classifier import classify_difficulty
from backend.services import history_service

logger = logging.getLogger(__name__)

# DB 연결 불가 시 재사용하는 DryRunResult
_DB_UNREACHABLE_RESULT = DryRunResult(
    is_success=False,
    executed_sql=None,
    explain_plan=None,
    error_message="DB 연결 실패: 연결 사전 검증에서 접속 불가 확인됨",
    error_hint=(
        "📌 **원인**: 변환 시작 시 PostgreSQL 연결 사전 검증에서 실패하여 Dry-run을 건너뛰었습니다.\n\n"
        "💡 **해결 방법**:\n"
        "  - 설정 메뉴에서 DB 호스트, 포트, 계정 정보가 올바른지 확인하세요\n"
        "  - DB 서버가 실행 중이고 네트워크 접근이 가능한지 확인하세요\n"
        "  - 방화벽 또는 VPN 설정으로 인해 접속이 차단되었을 수 있습니다"
    ),
)


def _test_db_connection(db_config: DBConfig) -> bool:
    """DB 연결 사전 검증 (1회만 수행)"""
    try:
        conn = psycopg2.connect(
            host=db_config.host,
            port=db_config.port,
            dbname=db_config.db_name,
            user=db_config.user,
            password=db_config.pw,
            connect_timeout=10,
            sslmode='require'
        )
        conn.close()
        return True
    except Exception as e:
        logger.warning("[Convert] DB 사전 연결 실패: %s", str(e).strip())
        return False


def process_conversion(request: ConvertRequest) -> ConvertResponse:
    """
    기존 동기식 변환 파이프라인 (기타 서비스 호환용)
    """
    total = len(request.queries)
    results = []
    
    # stream_conversion 제네레이터를 활용하여 로직 중복 제거
    for item in stream_conversion(request):
        if item["type"] == "complete":
            return ConvertResponse(**item["final_response"])
            
    # 위에서 return되지 않는 경우 (이론상 발생 불가)
    return ConvertResponse(
        project_id=request.project_id,
        xml_file_name=request.xml_file_name,
        queries=[],
    )


def stream_conversion(request: ConvertRequest):
    """
    Interface B 실시간 스트리밍 변환 파이프라인
    진행 상태와 개별 쿼리 결과를 yield 합니다.
    """
    db_config: Optional[DBConfig] = project_service.get_db_config(request.project_id)
    total_queries = len(request.queries)
    start_time = time.time()
    
    logger.info("[Convert] 시작 — project=%s, file=%s, queries=%d", request.project_id, request.xml_file_name, total_queries)

    # 효과적인 시스템 프롬프트 결정
    effective_system_prompt = request.system_prompt_override
    if not effective_system_prompt:
        project = project_service.get_project(request.project_id)
        if project and project.get("system_prompt"):
            effective_system_prompt = project["system_prompt"]

    yield {
        "type": "progress",
        "current": 0.1,
        "total": total_queries,
        "message": "데이터베이스 연결 확인 중...",
        "estimated_seconds": total_queries * 6
    }

    db_reachable = False
    if db_config:
        db_reachable = _test_db_connection(db_config)
    
    results: list[QueryResult] = []

    # 3. 쿼리별 순차 처리
    for idx, query in enumerate(request.queries, 1):
        # 3a. DDL 스키마 조회 단계
        yield {
            "type": "progress",
            "current": idx - 0.8,
            "total": total_queries,
            "message": f"[{idx}/{total_queries}] 스키마 분석 중: {query.query_id}",
            "estimated_seconds": (total_queries - idx + 1) * 6
        }
        
        try:
            schema_context = ""
            if db_reachable:
                schema_context = schema_fetcher.fetch_schema_context(
                    db_config, query.original_sql_xml
                )

            # 3b. LLM 변환 호출 단계
            yield {
                "type": "progress",
                "current": idx - 0.5,
                "total": total_queries,
                "message": f"[{idx}/{total_queries}] AI 변환 수행 중: {query.query_id}",
                "estimated_seconds": (total_queries - idx + 1) * 6 - 2
            }
            
            llm_response = llm_client.convert_query(
                original_sql_xml=query.original_sql_xml,
                schema_context=schema_context,
                tag_name=query.tag_name,
                system_prompt=effective_system_prompt
            )

            converted_sql = llm_response.get("converted_sql", query.original_sql_xml)
            conversion_log_raw = llm_response.get("conversion_log", [])
            difficulty_assessment = llm_response.get("difficulty_assessment", {})
            ai_guide_report = llm_response.get("ai_guide_report", "")
            confidence_score = difficulty_assessment.get("confidence", 0.0)
            token_usage = llm_response.get("_token_usage", {})
            input_tokens = token_usage.get("input_tokens", 0)
            output_tokens = token_usage.get("output_tokens", 0)

            conversion_log = [
                ConversionLogEntry(
                    category=log.get("category", "SYNTAX"),
                    before=log.get("before", ""),
                    after=log.get("after", ""),
                )
                for log in conversion_log_raw
                if isinstance(log, dict)
            ]

            # 3c. Dry-run 실행 단계
            yield {
                "type": "progress",
                "current": idx - 0.2,
                "total": total_queries,
                "message": f"[{idx}/{total_queries}] Dry-run 검증 중: {query.query_id}",
                "estimated_seconds": (total_queries - idx + 1) * 6 - 4
            }
            
            if db_reachable:
                dry_run_result = dryrun_service.execute_dry_run(db_config, converted_sql)
            else:
                dry_run_result = _DB_UNREACHABLE_RESULT

            difficulty_level = classify_difficulty(
                dry_run_result=dry_run_result,
                llm_assessment=difficulty_assessment,
                conversion_log=conversion_log_raw,
            )

            result = QueryResult(
                query_id=query.query_id,
                tag_name=query.tag_name,
                attributes=query.attributes,
                original_sql_xml=query.original_sql_xml,
                difficulty_level=difficulty_level,
                converted_sql=converted_sql,
                conversion_log=conversion_log,
                dry_run_result=dry_run_result,
                ai_guide_report=ai_guide_report,
                confidence_score=confidence_score,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        except Exception as e:
            logger.error("[Convert] query_id=%s 처리 실패: %s", query.query_id, str(e))
            result = QueryResult(
                query_id=query.query_id,
                tag_name=query.tag_name,
                attributes=query.attributes,
                original_sql_xml=query.original_sql_xml,
                difficulty_level=3,
                converted_sql=query.original_sql_xml,
                conversion_log=[],
                dry_run_result=DryRunResult(
                    is_success=False,
                    error_message=f"변환 처리 중 오류: {str(e)}",
                ),
                ai_guide_report=f"변환 중 시스템 오류가 발생했습니다: {str(e)}",
                confidence_score=0.0,
            )

        results.append(result)
        
        # 개별 결과 완료 전송
        yield {
            "type": "progress",
            "current": idx,
            "total": total_queries,
            "message": f"[{idx}/{total_queries}] 변환 완료: {query.query_id}",
            "estimated_seconds": (total_queries - idx) * 6
        }
        
        yield {
            "type": "query_result",
            "query_id": query.query_id,
            "data": result.dict()
        }

    # 최종 완료
    end_time = time.time()
    duration = round(end_time - start_time, 2)

    # 활성 모델 정보 가져오기
    active_model = llm_client._get_active_model()

    total_input_tokens = sum(r.input_tokens for r in results)
    total_output_tokens = sum(r.output_tokens for r in results)

    response = ConvertResponse(
        project_id=request.project_id,
        xml_file_name=request.xml_file_name,
        duration_seconds=duration,
        used_model=active_model,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        queries=results,
    )
    history_service.save_conversion_history(request, response)
    
    yield {
        "type": "complete",
        "final_response": response.dict()
    }
