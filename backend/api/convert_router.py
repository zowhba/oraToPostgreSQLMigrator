"""
Interface B — 쿼리 변환 메인 로직 라우터
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
import asyncio

from backend.schemas.convert import ConvertRequest, ConvertResponse
from backend.services import convert_service, history_service
from backend.services import database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["쿼리 변환 (Interface B)"])


@router.post("/convert", response_model=ConvertResponse)
async def convert_queries(req: ConvertRequest):
    """
    XML 파일 단위 쿼리 변환 (기존 동기식 API)
    """
    return convert_service.process_conversion(req)


@router.post("/convert-stream")
async def convert_queries_stream(req: ConvertRequest):
    """
    실시간 진행 상황을 스트리밍하는 변환 API (SSE 스타일)
    """
    logger.info(
        "[API] POST /api/convert-stream — project=%s, file=%s, queries=%d",
        req.project_id,
        req.xml_file_name,
        len(req.queries),
    )

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
async def get_history():
    """작업 히스토리 계층 구조 조회"""
    return {
        "status": "success",
        "data": history_service.get_history_hierarchy()
    }


@router.get("/history/list")
async def get_history_flat():
    """작업 히스토리 전체 목록 최신순 조회"""
    return {
        "status": "success",
        "data": history_service.get_history_list()
    }


@router.get("/history/{conversion_id}")
async def get_history_detail(conversion_id: int):
    """특정 변환 히스토리 상세 조회"""
    try:
        conn = database.get_connection()
        cur = conn.cursor(cursor_factory=database.RealDictCursor)

        # 마스터 정보
        cur.execute("SELECT * FROM conversions WHERE conversion_id = %s", (conversion_id,))
        master = cur.fetchone()
        if not master:
            raise HTTPException(status_code=404, detail="히스토리를 찾을 수 없습니다.")

        # 상세 쿼리 결과
        cur.execute("""
            SELECT * FROM query_conversions 
            WHERE conversion_id = %s 
            ORDER BY detail_id
        """, (conversion_id,))
        queries = cur.fetchall()
        cur.close()

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

        return {
            "status": "success",
            "data": {
                "project_id": master["project_id"],
                "xml_file_name": master["xml_file_name"],
                "queries": formatted_queries
            }
        }
    except Exception as e:
        logger.error("[History] 상세 조회 실패: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{conversion_id}")
async def delete_history(conversion_id: int):
    """특정 변환 히스토리 삭제 (하위 query_conversions 포함)"""
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
        raise HTTPException(status_code=500, detail=str(e))
