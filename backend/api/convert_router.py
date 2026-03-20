"""
Interface B — 쿼리 변환 메인 로직 라우터
"""
import logging
from fastapi import APIRouter

from backend.schemas.convert import ConvertRequest, ConvertResponse
from backend.services import convert_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["쿼리 변환 (Interface B)"])


@router.post("/convert", response_model=ConvertResponse)
async def convert_queries(req: ConvertRequest):
    """
    XML 파일 단위 쿼리 변환 (메인 API)

    FE가 파싱한 MyBatis XML 쿼리를 받아서:
    1. DDL 스키마 자동 조회
    2. Azure GPT-5.0 LLM 변환
    3. PostgreSQL Dry-run 검증
    4. Difficulty Level (1/2/3) 분류
    결과를 JSON으로 반환합니다.
    """
    logger.info(
        "[API] POST /api/convert — project=%s, file=%s, queries=%d",
        req.project_id,
        req.xml_file_name,
        len(req.queries),
    )
    return convert_service.process_conversion(req)
