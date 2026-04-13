"""
Interface B — 쿼리 변환 메인 로직 Pydantic 모델
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


# ────────────────────────────────────────────
# 요청 (FE → BE)
# ────────────────────────────────────────────

class QueryAttributes(BaseModel):
    """MyBatis 태그 속성 (동적 필드 허용)"""
    model_config = ConfigDict(extra="allow")

    parameterType: Optional[str] = None
    resultType: Optional[str] = None


class QueryUnit(BaseModel):
    """FE가 보내는 개별 쿼리 단위"""
    query_id: str = Field(..., description="MyBatis SQL ID")
    tag_name: str = Field(..., description="XML 태그 종류 (select, insert 등)")
    attributes: QueryAttributes = Field(default_factory=QueryAttributes)
    original_sql_xml: str = Field(
        ..., description="동적 태그 포함 원본 XML 조각 (Escaped)"
    )


class ConvertRequest(BaseModel):
    """Interface B 변환 요청"""
    project_id: str = Field(..., description="DB 매핑 및 DDL 조회를 위한 키값")
    xml_file_name: str = Field(..., description="원본 파일명", examples=["PlanMapper.xml"])
    mapper_namespace: str = Field(
        ..., description="원본 XML의 <mapper namespace> 값",
        examples=["com.skb.PlanMapper"],
    )
    file_created_at: str = Field(
        ..., description="요청 생성 일시 (YYYY-MM-DD HH:mm:ss)"
    )
    queries: list[QueryUnit]
    system_prompt_override: Optional[str] = Field(None, description="해당 세션에만 적용할 1회성 시스템 프롬프트")


# ────────────────────────────────────────────
# 응답 (BE → FE)
# ────────────────────────────────────────────

class ConversionLogEntry(BaseModel):
    """변환 이력 상세 1건"""
    category: str = Field(
        ..., description="변환 유형: JOIN, FUNCTION, SYNTAX, HINT, DATATYPE"
    )
    before: str = Field(..., description="Oracle 원본 문법 조각")
    after: str = Field(..., description="PostgreSQL 변환 문법 조각")


class DryRunResult(BaseModel):
    """DB 검증(Dry-run) 결과"""
    is_success: bool = Field(..., description="EXPLAIN 실행 성공 여부")
    executed_sql: Optional[str] = Field(None, description="실제 Dry-run에 사용된 SQL (MyBatis 태그 제거 후)")
    explain_plan: Optional[str] = Field(None, description="성공 시 실행 계획")
    error_message: Optional[str] = Field(None, description="실패 시 에러 메시지 (raw)")
    error_hint: Optional[str] = Field(None, description="실패 시 에러 원인 및 해결 방법 설명 (친절한 한국어)")


class QueryResult(BaseModel):
    """BE가 반환하는 개별 쿼리 결과"""
    query_id: str
    tag_name: str
    attributes: QueryAttributes
    original_sql_xml: str
    difficulty_level: int = Field(..., ge=1, le=3, description="1: 완전 자동, 2: AI 보정, 3: 수작업")
    converted_sql: str = Field(..., description="PostgreSQL 변환 결과물")
    conversion_log: list[ConversionLogEntry] = Field(default_factory=list)
    dry_run_result: DryRunResult
    ai_guide_report: str = Field("", description="전문가용 심층 리포트")
    confidence_score: float = Field(0.0, description="AI 변환 확신도 (0.0 ~ 1.0)")


class ConvertResponse(BaseModel):
    """Interface B 변환 응답"""
    project_id: str
    xml_file_name: str = Field("", description="원본 파일명")
    duration_seconds: float = Field(0.0, description="전체 변환 소요 시간")
    used_model: Optional[str] = Field(None, description="변환에 사용된 LLM 모델명")
    queries: list[QueryResult]
