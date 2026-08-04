"""
Interface B — 쿼리 변환 메인 로직 Pydantic 모델
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional


# ────────────────────────────────────────────
# 공통 정의
# ────────────────────────────────────────────

# 원본 파일 종류
#   xml   : MyBatis 매퍼 XML (기본값, 기존 동작)
#   excel : 엑셀 쿼리 목록 (XML과 동일 파이프라인)
#   sql   : 프로시저/함수 등 순수 SQL 스크립트 — Dry-run 미수행
SourceType = Literal["xml", "excel", "sql"]

# Dry-run을 수행하지 않는 소스 종류
DRYRUN_SKIP_SOURCE_TYPES: frozenset[str] = frozenset({"sql"})


def is_dryrun_skipped_source(source_type: Optional[str]) -> bool:
    """해당 소스 종류가 Dry-run 생략 대상인지 판별합니다."""
    return (source_type or "xml").lower() in DRYRUN_SKIP_SOURCE_TYPES


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
    query_id: str = Field(..., description="MyBatis SQL ID (.sql 소스인 경우 오브젝트명)")
    tag_name: str = Field(
        ...,
        description=(
            "XML 태그 종류 (select, insert 등). "
            ".sql 소스인 경우 오브젝트 종류 (procedure, function, package_body 등)"
        ),
    )
    attributes: QueryAttributes = Field(default_factory=QueryAttributes)
    original_sql_xml: str = Field(
        ...,
        description=(
            "동적 태그 포함 원본 XML 조각 (Escaped). "
            ".sql 소스인 경우 XML 래핑 없는 순수 SQL/PL-SQL 원문"
        ),
    )


class ConvertRequest(BaseModel):
    """Interface B 변환 요청"""
    project_id: str = Field(..., description="DB 매핑 및 DDL 조회를 위한 키값")
    xml_file_name: str = Field(..., description="원본 파일명", examples=["PlanMapper.xml"])
    mapper_namespace: str = Field(
        "", description="원본 XML의 <mapper namespace> 값 (.sql/엑셀 소스는 비어 있을 수 있음)",
        examples=["com.skb.PlanMapper"],
    )
    file_created_at: str = Field(
        ..., description="요청 생성 일시 (YYYY-MM-DD HH:mm:ss)"
    )
    source_type: SourceType = Field(
        "xml",
        description=(
            "원본 파일 종류. "
            "xml: MyBatis 매퍼 / excel: 엑셀 쿼리 목록 / "
            "sql: 프로시저·함수 등 순수 SQL 스크립트(Dry-run 미수행)"
        ),
    )
    queries: list[QueryUnit]
    system_prompt_override: Optional[str] = Field(None, description="해당 세션에만 적용할 1회성 시스템 프롬프트")
    model_override: Optional[str] = Field(None, description="해당 요청에만 적용할 1회성 LLM 모델 (전역 active_model 무시)")


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
    is_skipped: bool = Field(
        False,
        description=(
            "Dry-run을 아예 수행하지 않은 경우 True. "
            "실패(is_success=False)와 구분되며 난이도 분류에서 시그널로 사용되지 않습니다."
        ),
    )
    skip_reason: Optional[str] = Field(None, description="Dry-run을 생략한 사유")
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
    input_tokens: int = Field(0, description="LLM 입력 토큰 수")
    output_tokens: int = Field(0, description="LLM 출력 토큰 수")


class ConvertResponse(BaseModel):
    """Interface B 변환 응답"""
    project_id: str
    xml_file_name: str = Field("", description="원본 파일명")
    source_type: SourceType = Field("xml", description="원본 파일 종류 (xml/excel/sql)")
    duration_seconds: float = Field(0.0, description="전체 변환 소요 시간")
    used_model: Optional[str] = Field(None, description="변환에 사용된 LLM 모델명")
    total_input_tokens: int = Field(0, description="전체 입력 토큰 합계")
    total_output_tokens: int = Field(0, description="전체 출력 토큰 합계")
    queries: list[QueryResult]
