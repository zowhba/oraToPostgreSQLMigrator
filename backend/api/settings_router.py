from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from backend.api.deps import require_actor, require_admin, require_viewer
from backend.services import database as app_db
import json
import logging

router = APIRouter(prefix="/api/settings", tags=["Settings"])
logger = logging.getLogger(__name__)

# 클라이언트에 절대 노출하면 안 되는 설정 키
SENSITIVE_SETTING_KEYS = {"jwt_secret", "admin_password"}

class AppSetting(BaseModel):
    key: str
    value: str

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

@router.get("", dependencies=[Depends(require_actor)])
async def get_settings():
    """모든 설정을 조회합니다 (민감 키 제외) — Actor 이상"""
    try:
        conn = app_db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT setting_key, setting_value FROM app_settings")
            rows = cur.fetchall()
            return {row[0]: row[1] for row in rows if row[0] not in SENSITIVE_SETTING_KEYS}
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        # 드라이버 원문 메시지는 내부 구조를 노출하므로 로그에만 남긴다
        raise HTTPException(status_code=500, detail="설정 처리 중 오류가 발생했습니다.")

@router.post("", dependencies=[Depends(require_admin)])
async def update_setting(setting: AppSetting):
    """설정을 업데이트합니다 — Admin 전용"""
    if setting.key in SENSITIVE_SETTING_KEYS:
        raise HTTPException(status_code=400, detail="변경할 수 없는 설정 키입니다.")
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
        # 드라이버 원문 메시지는 내부 구조를 노출하므로 로그에만 남긴다
        raise HTTPException(status_code=500, detail="설정 처리 중 오류가 발생했습니다.")

@router.get("/active-model", dependencies=[Depends(require_viewer)])
async def get_active_model():
    """현재 활성화된 LLM 모델을 조회합니다 — 로그인한 모든 사용자"""
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
# LLM 모델 활성화 관리
# ─────────────────────────────────────────────

@router.get("/enabled-models", dependencies=[Depends(require_viewer)])
async def get_enabled_models():
    """현재 활성화된 LLM 모델 ID 목록을 반환합니다 — 로그인한 모든 사용자"""
    try:
        raw = _get_setting('enabled_models', '["gpt-5.2-chat","haiku-4.5","sonnet-4.5","opus-4.6"]')
        return {"models": json.loads(raw)}
    except Exception as e:
        logger.error(f"Failed to get enabled models: {e}")
        return {"models": ["gpt-5.2-chat", "haiku-4.5", "sonnet-4.5", "opus-4.6"]}


@router.post("/enabled-models", dependencies=[Depends(require_admin)])
async def set_enabled_models(payload: EnabledModels):
    """활성화된 LLM 모델 목록을 갱신합니다 — Admin 전용"""
    try:
        if not payload.models:
            raise HTTPException(status_code=400, detail="최소 1개 이상의 모델이 활성화되어야 합니다.")
        _set_setting('enabled_models', json.dumps(payload.models))
        return {"status": "success", "models": payload.models}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set enabled models: {e}")
        # 드라이버 원문 메시지는 내부 구조를 노출하므로 로그에만 남긴다
        raise HTTPException(status_code=500, detail="설정 처리 중 오류가 발생했습니다.")


# ─────────────────────────────────────────────
# LLM 과금 정책 관리 API
# ─────────────────────────────────────────────

@router.get("/pricing", dependencies=[Depends(require_actor)])
async def get_pricing():
    """LLM 모델별 과금 정책을 조회합니다 — Actor 이상"""
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
        # 드라이버 원문 메시지는 내부 구조를 노출하므로 로그에만 남긴다
        raise HTTPException(status_code=500, detail="설정 처리 중 오류가 발생했습니다.")


@router.post("/pricing", dependencies=[Depends(require_admin)])
async def update_pricing(payload: LlmPricingUpdate):
    """LLM 모델별 과금 정책을 일괄 업데이트합니다 — Admin 전용"""
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
        # 드라이버 원문 메시지는 내부 구조를 노출하므로 로그에만 남긴다
        raise HTTPException(status_code=500, detail="설정 처리 중 오류가 발생했습니다.")
