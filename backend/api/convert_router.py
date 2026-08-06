"""
Interface B — 쿼리 변환 메인 로직 라우터
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import json

from backend.api.deps import (
    CurrentUser,
    allowed_project_ids,
    ensure_project_access,
    require_actor,
    require_admin,
    require_viewer,
)
from backend.schemas.convert import ConvertRequest, ConvertResponse
from backend.services import convert_service, history_service
from backend.services import database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["쿼리 변환 (Interface B)"])


@router.post("/convert", response_model=ConvertResponse)
async def convert_queries(req: ConvertRequest, user: CurrentUser = Depends(require_actor)):
    """
    XML 파일 단위 쿼리 변환 (기존 동기식 API) — Actor 이상
    """
    logger.info("[API] POST /api/convert — user=%s", user["username"])
    ensure_project_access(user, req.project_id)
    return convert_service.process_conversion(req)


@router.post("/convert-stream")
async def convert_queries_stream(req: ConvertRequest, user: CurrentUser = Depends(require_actor)):
    """
    실시간 진행 상황을 스트리밍하는 변환 API (SSE 스타일) — Actor 이상
    """
    logger.info(
        "[API] POST /api/convert-stream — user=%s, project=%s, file=%s, queries=%d",
        user["username"],
        req.project_id,
        req.xml_file_name,
        len(req.queries),
    )
    ensure_project_access(user, req.project_id)

    def event_generator():
        for item in convert_service.stream_conversion(req):
            # 표준 SSE(Server-Sent Events) 형식으로 전송하여 브라우저 버퍼링 방지
            # 규격: "data: {JSON}\n\n"
            data_str = json.dumps(item, ensure_ascii=False)
            yield f"data: {data_str}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
        }
    )


@router.get("/history")
async def get_history(user: CurrentUser = Depends(require_viewer)):
    """작업 히스토리 계층 구조 조회 — 접근 허용된 프로젝트만"""
    return {
        "status": "success",
        "data": history_service.get_history_hierarchy(allowed_project_ids(user))
    }


@router.get("/history/list")
async def get_history_flat(user: CurrentUser = Depends(require_viewer)):
    """작업 히스토리 전체 목록 최신순 조회 — 접근 허용된 프로젝트만"""
    return {
        "status": "success",
        "data": history_service.get_history_list(allowed_project_ids(user))
    }


@router.get("/history/{conversion_id}")
async def get_history_detail(conversion_id: int, user: CurrentUser = Depends(require_viewer)):
    """특정 변환 히스토리 상세 조회 — 접근 허용된 프로젝트만"""
    try:
        conn = database.get_connection()
        # with 블록으로 예외 경로에서도 커서가 닫히도록 보장
        with conn.cursor(cursor_factory=database.RealDictCursor) as cur:
            # 마스터 정보 (프로젝트명 포함)
            cur.execute("""
                SELECT c.*, p.project_name
                FROM conversions c
                LEFT JOIN projects p ON c.project_id = p.project_id
                WHERE c.conversion_id = %s
            """, (conversion_id,))
            master = cur.fetchone()
            if not master:
                raise HTTPException(status_code=404, detail="히스토리를 찾을 수 없습니다.")

            # 접근 허용 프로젝트 밖의 이력은 존재 여부도 노출하지 않는다
            ensure_project_access(user, master["project_id"])

            # 상세 쿼리 결과
            cur.execute("""
                SELECT * FROM query_conversions
                WHERE conversion_id = %s
                ORDER BY detail_id
            """, (conversion_id,))
            queries = cur.fetchall()

        # 데이터 가공 (JSON 필드 파싱)
        formatted_queries = []
        for q in queries:
            formatted_queries.append({
                "query_id": q["query_id"],
                "tag_name": q["tag_name"],
                "difficulty_level": q["difficulty_level"],
                "original_sql_xml": q["original_sql_xml"],
                "converted_sql": q["converted_sql"],
                "conversion_log": json.loads(q["conversion_log"]) if isinstance(q["conversion_log"], str) else q["conversion_log"],
                "dry_run_result": json.loads(q["dry_run_result"]) if isinstance(q["dry_run_result"], str) else q["dry_run_result"],
                "ai_guide_report": q["ai_guide_report"],
                "confidence_score": q.get("confidence_score", 0.0)
            })

        created_at = master.get("created_at")
        return {
            "status": "success",
            "data": {
                "conversion_id": master["conversion_id"],
                "project_id": master["project_id"],
                "project_name": master.get("project_name") or "알 수 없는 프로젝트",
                "xml_file_name": master["xml_file_name"],
                "used_model": master.get("used_model"),
                "duration_seconds": master.get("duration_seconds"),
                "total_queries": master.get("total_queries"),
                "total_input_tokens": master.get("total_input_tokens") or 0,
                "total_output_tokens": master.get("total_output_tokens") or 0,
                "created_at": created_at.isoformat() + "Z" if created_at else None,
                "levels": {
                    "l1": master.get("l1_count") or 0,
                    "l2": master.get("l2_count") or 0,
                    "l3": master.get("l3_count") or 0,
                },
                "queries": formatted_queries
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[History] 상세 조회 실패: %s", str(e))
        raise HTTPException(status_code=500, detail="히스토리 조회 중 오류가 발생했습니다.")


@router.delete("/history/{conversion_id}", dependencies=[Depends(require_admin)])
async def delete_history(conversion_id: int):
    """특정 변환 히스토리 삭제 (하위 query_conversions 포함) — Admin 전용"""
    try:
        conn = database.get_connection()
        cur = conn.cursor()

        cur.execute("SELECT conversion_id FROM conversions WHERE conversion_id = %s", (conversion_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="히스토리를 찾을 수 없습니다.")

        # query_conversions는 ON DELETE CASCADE로 자동 삭제됨
        cur.execute("DELETE FROM conversions WHERE conversion_id = %s", (conversion_id,))
        conn.commit()
        cur.close()

        logger.info("[History] 히스토리 삭제 완료: conversion_id=%d", conversion_id)
        return {"status": "success", "message": f"히스토리 #{conversion_id}이 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[History] 히스토리 삭제 실패: %s", str(e))
        raise HTTPException(status_code=500, detail="히스토리 삭제 중 오류가 발생했습니다.")
