"""
쿼리 변환 오케스트레이션 서비스
LLM 변환 → Dry-run → Difficulty 분류의 전체 파이프라인
"""
import logging
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
    explain_plan=None,
    error_message="DB 연결 실패: 연결 사전 검증에서 접속 불가 확인됨",
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
            connect_timeout=5,
        )
        conn.close()
        return True
    except Exception as e:
        logger.warning("[Convert] DB 사전 연결 실패: %s", str(e).strip())
        return False


def process_conversion(request: ConvertRequest) -> ConvertResponse:
    """
    Interface B 메인 변환 파이프라인

    1. project_id로 DB 접속정보 조회
    2. DB 연결 사전 검증 (1회) — 실패 시 schema/dryrun 전체 스킵
    3. 쿼리별 순차 처리:
       a. schema_fetcher로 테이블 DDL 조회 (DB 가용 시)
       b. llm_client로 LLM 변환 호출
       c. LLM 응답 파싱
       d. dryrun_service로 Dry-run 실행 (DB 가용 시)
       e. difficulty_classifier로 Level 분류
       f. QueryResult 조합
    4. ConvertResponse 반환
    """
    # 1. DB 접속 정보 조회
    db_config: Optional[DBConfig] = project_service.get_db_config(request.project_id)
    if not db_config:
        logger.error("[Convert] 프로젝트 '%s'를 찾을 수 없습니다.", request.project_id)
        return ConvertResponse(
            project_id=request.project_id,
            queries=[
                QueryResult(
                    query_id=q.query_id,
                    tag_name=q.tag_name,
                    attributes=q.attributes,
                    original_sql_xml=q.original_sql_xml,
                    difficulty_level=3,
                    converted_sql=q.original_sql_xml,
                    conversion_log=[],
                    dry_run_result=DryRunResult(
                        is_success=False,
                        error_message=f"프로젝트 '{request.project_id}'를 찾을 수 없습니다.",
                    ),
                    ai_guide_report=f"프로젝트 '{request.project_id}'가 등록되지 않았습니다. "
                                    "먼저 Interface A를 통해 프로젝트를 등록하세요.",
                )
                for q in request.queries
            ],
        )

    # 2. DB 연결 사전 검증 (1회)
    db_reachable = _test_db_connection(db_config)
    if db_reachable:
        logger.info("[Convert] DB 연결 확인 완료 (%s:%d/%s)", db_config.host, db_config.port, db_config.db_name)
    else:
        logger.warning(
            "[Convert] DB 연결 불가 — schema 조회 및 dry-run을 건너뜁니다. "
            "LLM 변환만 수행합니다."
        )

    logger.info(
        "[Convert] 시작 — project=%s, file=%s, queries=%d, db_reachable=%s",
        request.project_id,
        request.xml_file_name,
        len(request.queries),
        db_reachable,
    )

    results: list[QueryResult] = []

    # 3. 쿼리별 순차 처리
    for idx, query in enumerate(request.queries, 1):
        logger.info(
            "[Convert] [%d/%d] query_id=%s, tag=%s",
            idx, len(request.queries), query.query_id, query.tag_name,
        )

        try:
            # 3a. DDL 스키마 조회 (DB 가용 시만)
            if db_reachable:
                schema_context = schema_fetcher.fetch_schema_context(
                    db_config, query.original_sql_xml
                )
            else:
                schema_context = ""

            # 3b. LLM 변환 호출
            llm_response = llm_client.convert_query(
                original_sql_xml=query.original_sql_xml,
                schema_context=schema_context,
                tag_name=query.tag_name,
            )

            # 3c. LLM 응답 파싱
            converted_sql = llm_response.get("converted_sql", query.original_sql_xml)
            conversion_log_raw = llm_response.get("conversion_log", [])
            difficulty_assessment = llm_response.get("difficulty_assessment", {})
            ai_guide_report = llm_response.get("ai_guide_report", "")

            # conversion_log를 Pydantic 모델로 변환
            conversion_log = [
                ConversionLogEntry(
                    category=log.get("category", "SYNTAX"),
                    before=log.get("before", ""),
                    after=log.get("after", ""),
                )
                for log in conversion_log_raw
                if isinstance(log, dict)
            ]

            # 3d. Dry-run 실행 (DB 가용 시만)
            if db_reachable:
                dry_run_result = dryrun_service.execute_dry_run(db_config, converted_sql)
            else:
                dry_run_result = _DB_UNREACHABLE_RESULT

            # 3e. Difficulty Level 분류
            difficulty_level = classify_difficulty(
                dry_run_result=dry_run_result,
                llm_assessment=difficulty_assessment,
                conversion_log=conversion_log_raw,
            )

            # 3f. QueryResult 조합
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
            )

        except Exception as e:
            # 개별 쿼리 처리 실패 → Level 3, 나머지 계속
            logger.error(
                "[Convert] query_id=%s 처리 실패: %s",
                query.query_id, str(e),
            )
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
                ai_guide_report=f"변환 중 시스템 오류가 발생했습니다: {str(e)}. 수동 변환이 필요합니다.",
            )

        results.append(result)

    logger.info(
        "[Convert] 완료 — 총 %d건 (L1=%d, L2=%d, L3=%d)",
        len(results),
        sum(1 for r in results if r.difficulty_level == 1),
        sum(1 for r in results if r.difficulty_level == 2),
        sum(1 for r in results if r.difficulty_level == 3),
    )

    response = ConvertResponse(
        project_id=request.project_id,
        xml_file_name=request.xml_file_name,
        queries=results,
    )

    # 4. 변환 히스토리 DB 저장 (영속화)
    history_service.save_conversion_history(request, response)

    return response

