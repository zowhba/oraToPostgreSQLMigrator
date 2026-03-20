"""
변환 히스토리 영속화 서비스
conversions 및 query_conversions 테이블에 결과 저장
"""
import json
import logging
from backend.services import database
from backend.schemas.convert import ConvertRequest, ConvertResponse

logger = logging.getLogger(__name__)

def save_conversion_history(request: ConvertRequest, response: ConvertResponse):
    """
    변환 요청 및 응답 결과를 DB에 저장합니다.
    """
    try:
        conn = database.get_connection()
        cur = conn.cursor()

        # 1. conversions 마스터 테이블 저장
        l1_count = sum(1 for r in response.queries if r.difficulty_level == 1)
        l2_count = sum(1 for r in response.queries if r.difficulty_level == 2)
        l3_count = sum(1 for r in response.queries if r.difficulty_level == 3)

        cur.execute(
            """
            INSERT INTO conversions (
                project_id, xml_file_name, total_queries, l1_count, l2_count, l3_count
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING conversion_id
            """,
            (
                request.project_id,
                request.xml_file_name,
                len(response.queries),
                l1_count,
                l2_count,
                l3_count
            )
        )
        conversion_id = cur.fetchone()[0]

        # 2. query_conversions 상세 테이블 저장
        for res in response.queries:
            # conversion_log를 JSON 문자열로 변환
            log_json = json.dumps([log.model_dump() for log in res.conversion_log], ensure_ascii=False)
            
            # dry_run_result를 JSON 문자열로 변환
            dry_run_json = json.dumps(res.dry_run_result.model_dump(), ensure_ascii=False)

            cur.execute(
                """
                INSERT INTO query_conversions (
                    conversion_id, query_id, tag_name, difficulty_level,
                    original_sql_xml, converted_sql, conversion_log,
                    dry_run_success, dry_run_result, ai_guide_report
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    conversion_id,
                    res.query_id,
                    res.tag_name,
                    res.difficulty_level,
                    res.original_sql_xml,
                    res.converted_sql,
                    log_json,
                    res.dry_run_result.is_success,
                    dry_run_json,
                    res.ai_guide_report
                )
            )

        logger.info("[History] 변환 히스토리 저장 완료 (ID: %d, Queries: %d)", conversion_id, len(response.queries))

    except Exception as e:
        logger.error("[History] 히스토리 저장 중 오류 발생: %s", str(e))
        # 히스토리 저장은 부가 기능이므로 메인 흐름을 방해하지 않도록 예외를 로깅만 하고 상위로 던지지 않음
