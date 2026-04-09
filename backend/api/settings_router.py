from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services import database as app_db
import logging

router = APIRouter(prefix="/api/settings", tags=["Settings"])
logger = logging.getLogger(__name__)

class AppSetting(BaseModel):
    key: str
    value: str

@router.get("")
async def get_settings():
    """모든 설정을 조회합니다."""
    try:
        conn = app_db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT setting_key, setting_value FROM app_settings")
            rows = cur.fetchall()
            return {row[0]: row[1] for row in rows}
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def update_setting(setting: AppSetting):
    """설정을 업데이트합니다."""
    try:
        conn = app_db.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO app_settings (setting_key, setting_value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (setting_key) DO UPDATE 
                SET setting_value = EXCLUDED.setting_value, 
                    updated_at = EXCLUDED.updated_at
            """, (setting.key, setting.value))
            return {"status": "success", "key": setting.key, "value": setting.value}
    except Exception as e:
        logger.error(f"Failed to update setting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active-model")
async def get_active_model():
    """현재 활성화된 LLM 모델을 조회합니다."""
    try:
        conn = app_db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'active_model'")
            row = cur.fetchone()
            if row:
                return {"active_model": row[0]}
            return {"active_model": "gpt-5.2-chat"}  # Default
    except Exception as e:
        logger.error(f"Failed to get active model: {e}")
        return {"active_model": "gpt-5.2-chat"}
