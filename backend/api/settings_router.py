from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from backend.services import database as app_db
import json
import logging

router = APIRouter(prefix="/api/settings", tags=["Settings"])
logger = logging.getLogger(__name__)

class AppSetting(BaseModel):
    key: str
    value: str

class AdminLogin(BaseModel):
    password: str

class AdminPasswordChange(BaseModel):
    old_password: str
    new_password: str

class EnabledModels(BaseModel):
    models: List[str]

class LlmPricingItem(BaseModel):
    model_id: str
    display_name: str
    input_price: float
    output_price: float

class LlmPricingUpdate(BaseModel):
    pricing: List[LlmPricingItem]


def _get_setting(key: str, default: str = "") -> str:
    conn = app_db.get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = %s", (key,))
        row = cur.fetchone()
        return row[0] if row else default


def _set_setting(key: str, value: str) -> None:
    conn = app_db.get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO app_settings (setting_key, setting_value, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (setting_key) DO UPDATE
            SET setting_value = EXCLUDED.setting_value,
                updated_at = EXCLUDED.updated_at
        """, (key, value))

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


# ─────────────────────────────────────────────
# Admin 모드 관련 API
# ─────────────────────────────────────────────

@router.get("/enabled-models")
async def get_enabled_models():
    """현재 활성화된 LLM 모델 ID 목록을 반환합니다."""
    try:
        raw = _get_setting('enabled_models', '["gpt-5.2-chat","haiku-4.5","sonnet-4.5","opus-4.6"]')
        return {"models": json.loads(raw)}
    except Exception as e:
        logger.error(f"Failed to get enabled models: {e}")
        return {"models": ["gpt-5.2-chat", "haiku-4.5", "sonnet-4.5", "opus-4.6"]}


@router.post("/enabled-models")
async def set_enabled_models(payload: EnabledModels):
    """활성화된 LLM 모델 목록을 갱신합니다 (Admin 전용)."""
    try:
        if not payload.models:
            raise HTTPException(status_code=400, detail="최소 1개 이상의 모델이 활성화되어야 합니다.")
        _set_setting('enabled_models', json.dumps(payload.models))
        return {"status": "success", "models": payload.models}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set enabled models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/login")
async def admin_login(payload: AdminLogin):
    """Admin 패스워드 검증."""
    try:
        stored = _get_setting('admin_password', '8838')
        if payload.password == stored:
            return {"status": "success", "ok": True}
        return {"status": "error", "ok": False, "message": "패스워드가 일치하지 않습니다."}
    except Exception as e:
        logger.error(f"Admin login failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/password")
async def change_admin_password(payload: AdminPasswordChange):
    """Admin 패스워드 변경."""
    try:
        stored = _get_setting('admin_password', '8838')
        if payload.old_password != stored:
            raise HTTPException(status_code=403, detail="기존 패스워드가 일치하지 않습니다.")
        if not payload.new_password or len(payload.new_password) < 4:
            raise HTTPException(status_code=400, detail="새 패스워드는 4자 이상이어야 합니다.")
        _set_setting('admin_password', payload.new_password)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change admin password failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# LLM 과금 정책 관리 API
# ─────────────────────────────────────────────

@router.get("/pricing")
async def get_pricing():
    """LLM 모델별 과금 정책을 조회합니다."""
    try:
        conn = app_db.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT model_id, display_name, input_price, output_price, currency, price_unit, updated_at
                FROM llm_pricing ORDER BY sort_order, model_id
            """)
            rows = cur.fetchall()
            return {
                "status": "success",
                "pricing": [
                    {
                        "model_id": r[0],
                        "display_name": r[1],
                        "input_price": r[2],
                        "output_price": r[3],
                        "currency": r[4],
                        "price_unit": r[5],
                        "updated_at": r[6].isoformat() if r[6] else None
                    }
                    for r in rows
                ]
            }
    except Exception as e:
        logger.error(f"Failed to get pricing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pricing")
async def update_pricing(payload: LlmPricingUpdate):
    """LLM 모델별 과금 정책을 일괄 업데이트합니다."""
    try:
        conn = app_db.get_connection()
        with conn.cursor() as cur:
            for item in payload.pricing:
                cur.execute("""
                    INSERT INTO llm_pricing (model_id, display_name, input_price, output_price, updated_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (model_id) DO UPDATE
                    SET display_name = EXCLUDED.display_name,
                        input_price = EXCLUDED.input_price,
                        output_price = EXCLUDED.output_price,
                        updated_at = EXCLUDED.updated_at
                """, (item.model_id, item.display_name, item.input_price, item.output_price))
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to update pricing: {e}")
        raise HTTPException(status_code=500, detail=str(e))
