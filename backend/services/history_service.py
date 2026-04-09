"""
변환 히스토리 영속화 서비스
conversions 및 query_conversions 테이블에 결과 저장
"""
import json
import logging
import time
from typing import List, Dict
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
                project_id, xml_file_name, total_queries, l1_count, l2_count, l3_count, duration_seconds, used_model
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING conversion_id
            """,
            (
                request.project_id,
                request.xml_file_name,
                len(response.queries),
                l1_count,
                l2_count,
                l3_count,
                response.duration_seconds,
                response.used_model
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

def get_history_hierarchy() -> List[Dict]:
    """
    1레벨: 프로젝트, 2레벨: 파일, 3레벨: 시도(Attempt) 계층으로 히스토리 반환
    """
    try:
        conn = database.get_connection()
        cur = conn.cursor(cursor_factory=database.RealDictCursor)

        # 모든 변환 기록 조회 (프로젝트 정보 포함)
        cur.execute("""
            SELECT 
                c.conversion_id, 
                c.project_id, 
                p.project_name, 
                c.xml_file_name, 
                c.total_queries, 
                c.l1_count, c.l2_count, c.l3_count, 
                c.duration_seconds, 
                c.used_model,
                c.created_at,
                (SELECT COUNT(*) FROM query_conversions qc WHERE qc.conversion_id = c.conversion_id AND qc.dry_run_success = TRUE) as success_count
            FROM conversions c
            LEFT JOIN projects p ON c.project_id = p.project_id
            ORDER BY p.project_name, c.xml_file_name, c.created_at DESC
        """)
        rows = cur.fetchall()
        cur.close()

        # 계층 구조 조립
        projects_dict = {}

        for row in rows:
            pid = row['project_id']
            pname = row['project_name'] or "알 수 없는 프로젝트"
            fname = row['xml_file_name'] or "unknown.xml"

            if pid not in projects_dict:
                projects_dict[pid] = {
                    "project_id": pid,
                    "project_name": pname,
                    "files": {}
                }

            if fname not in projects_dict[pid]["files"]:
                projects_dict[pid]["files"][fname] = {
                    "file_name": fname,
                    "attempts": []
                }

            # 시도 정보 추가
            projects_dict[pid]["files"][fname]["attempts"].append({
                "conversion_id": row['conversion_id'],
                "timestamp": row['created_at'].isoformat(),
                "total": row['total_queries'],
                "success": row['success_count'],
                "duration": row['duration_seconds'],
                "used_model": row['used_model'],
                "levels": {
                    "l1": row['l1_count'],
                    "l2": row['l2_count'],
                    "l3": row['l3_count']
                }
            })

        # Dictionary를 UI용 Array로 변환
        result = []
        for pid, pdata in projects_dict.items():
            files_list = []
            for fname, fdata in pdata["files"].items():
                files_list.append(fdata)
            
            pdata["files"] = files_list
            result.append(pdata)

        return result
    except Exception as e:
        logger.error("[History] 히스토리 조회 실패: %s", str(e))
        return []

def get_history_list() -> List[Dict]:
    """
    모든 변환 시도를 최신순으로 평면 목록(Flat List)으로 반환
    """
    try:
        conn = database.get_connection()
        cur = conn.cursor(cursor_factory=database.RealDictCursor)

        cur.execute("""
            SELECT 
                c.conversion_id, 
                c.project_id, 
                p.project_name, 
                c.xml_file_name, 
                c.total_queries, 
                c.l1_count, c.l2_count, c.l3_count, 
                c.duration_seconds, 
                c.used_model,
                c.created_at,
                (SELECT COUNT(*) FROM query_conversions qc WHERE qc.conversion_id = c.conversion_id AND qc.dry_run_success = TRUE) as success_count
            FROM conversions c
            LEFT JOIN projects p ON c.project_id = p.project_id
            ORDER BY c.created_at DESC
        """)
        rows = cur.fetchall()
        cur.close()

        # 데이터 가공
        result = []
        for row in rows:
            result.append({
                "conversion_id": row['conversion_id'],
                "project_id": row['project_id'],
                "project_name": row['project_name'] or "알 수 없는 프로젝트",
                "file_name": row['xml_file_name'] or "unknown.xml",
                "timestamp": row['created_at'].isoformat(),
                "total": row['total_queries'],
                "success": row['success_count'],
                "duration": row['duration_seconds'],
                "used_model": row['used_model'],
                "levels": {
                    "l1": row['l1_count'],
                    "l2": row['l2_count'],
                    "l3": row['l3_count']
                }
            })

        return result
    except Exception as e:
        logger.error("[History] 평면 히스토리 조회 실패: %s", str(e))
        return []
