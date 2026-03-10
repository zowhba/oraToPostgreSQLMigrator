# 📋 AI 쿼리 변환 시스템 최종 통합 연동 규격서 (v1.7)

본 규격서는 **AI 기반 Oracle → PostgreSQL 쿼리 변환 자동화 시스템**의 Frontend(고급)와 Backend(특급) 간의 효율적인 병렬 개발을 위해 데이터 구조와 통신 샘플을 인터페이스별로 명확히 정의합니다.

---

## 1. 프로젝트 개요
- **목적**: AI를 활용한 Oracle MyBatis 쿼리의 PostgreSQL 자동 변환 및 검증. [cite: 5, 6]
- **주요 전략**: 지능형 3단계 분류, DDL 스키마 인지, Dry Run 실시간 검증. [cite: 7, 39, 48]
- **담당자**: OSS서비스2팀 오지웅, 박세희. [cite: 12]

---

## 2. [Interface A] 프로젝트-DB 매핑 설정 (관리용)
사용자가 프로젝트를 생성하고, 해당 프로젝트가 사용할 대상 PostgreSQL 접속 정보를 등록합니다.

### 2.1. Payload 규격
| 필드명 | 타입 | 필수 | 설명 |
| :--- | :--- | :---: | :--- |
| **`project_id`** | String | Y | 프로젝트 고유 ID (예: `PRJ_SKB_001`) |
| **`project_name`** | String | Y | 프로젝트 명칭 |
| **`db_config`** | Object | Y | 접속 정보 (`host`, `port`, `db_name`, `user`, `pw`) |

### 2.2. 통신 샘플 (Interface A)
**[Request]**
```json
{
  "project_id": "PRJ_SKB_001",
  "project_name": "SKB 차세대 마이그레이션",
  "db_config": {
    "host": "10.1.2.3",
    "port": 5432,
    "db_name": "target_pg_db",
    "user": "migrator",
    "pw": "password123!"
  }
}
```
**[Response]**
```json
{
  "status": "success",
  "message": "프로젝트 DB 설정이 완료되었습니다.",
  "project_id": "PRJ_SKB_001"
}
```

---

## 3. [Interface B] 쿼리 변환 메인 로직 (파일 단위)
Frontend가 XML을 파싱하여 JSON으로 전달하면, Backend가 DDL 인지 기반 AI 변환 및 DB 검증 후 응답합니다. [cite: 13, 14, 23]

### 3.1. 요청/응답 데이터 규격
#### **(가) 전역 메타데이터 (Global Context)**
| 필드명 | 타입 | 필수 | 설명 |
| :--- | :--- | :---: | :--- |
| **`project_id`** | String | Y | DB 매핑 및 DDL 조회를 위한 키값 |
| **`xml_file_name`** | String | Y | 원본 파일명 (예: UserMapper.xml) |
| **`mapper_namespace`** | String | Y | 원본 XML의 `<mapper namespace="...">` 값 |
| **`file_created_at`** | String | Y | 요청 생성 일시 (`YYYY-MM-DD HH:mm:ss`) |

#### **(나) 쿼리 단위 데이터 (Query Unit)**
| 필드명 | 타입 | 발신(FE) | 수신(BE) | 설명 |
| :--- | :--- | :---: | :---: | :--- |
| **`query_id`** | String | **Y** | **Y** | MyBatis SQL ID |
| **`tag_name`** | String | **Y** | **Y** | XML 태그 종류 (select, insert 등) |
| **`attributes`** | Object | **Y** | **Y** | 원본 태그의 모든 속성 (parameterType 등) |
| **`original_sql_xml`** | String | **Y** | **Y** | 동적 태그 포함 원본 XML 조각 (Escaped) |
| **`difficulty_level`** | Integer | - | **Y** | 1(완전 자동), 2(AI 보정), 3(전문가 수동) 분류 [cite: 15, 16, 33] |
| **`converted_sql`** | String | - | **Y** | PostgreSQL 변환 결과물 [cite: 35] |
| **`conversion_log`** | Array | - | **Y** | 변환 이력 상세 (아래 '다'항 참조) |
| **`dry_run_result`** | Object | - | **Y** | DB 검증 결과 (아래 '다'항 참조) |
| **`ai_guide_report`** | String | - | **Y** | 전문가용 심층 리포트 [cite: 22] |

#### **(다) 상세 데이터 객체 정의**
**① `conversion_log` (배열)**
- **`category`**: 변환 유형 (`JOIN`, `FUNCTION`, `SYNTAX`, `HINT`, `DATATYPE`)
- **`before`**: Oracle 원본 문법 조각
- **`after`**: PostgreSQL 변환 문법 조각

**② `dry_run_result` (객체)**
- **`is_success`**: Boolean (실행 성공 여부) [cite: 49]
- **`explain_plan`**: String (성공 시 PostgreSQL 실행 계획) [cite: 49]
- **`error_message`**: String (실패 시 DB 에러 메시지) [cite: 49]

### 3.2. 통신 샘플 (Interface B)
**[Request: FE → BE]**
```json
{
  "project_id": "PRJ_SKB_001",
  "xml_file_name": "PlanMapper.xml",
  "mapper_namespace": "com.skb.PlanMapper",
  "file_created_at": "2026-03-03 15:00:00",
  "queries": [
    {
      "query_id": "selectPlanResult",
      "tag_name": "select",
      "attributes": { "parameterType": "map", "resultType": "vo" },
      "original_sql_xml": "<select id=\"selectPlanResult\">SELECT NVL(A, B) FROM T WHERE C(+) = D</select>"
    }
  ]
}
```

**[Response: BE → FE]**
```json
{
  "project_id": "PRJ_SKB_001",
  "queries": [
    {
      "query_id": "selectPlanResult",
      "difficulty_level": 2,
      "converted_sql": "SELECT COALESCE(A, B) FROM T LEFT OUTER JOIN ...",
      "conversion_log": [
        { "category": "FUNCTION", "before": "NVL", "after": "COALESCE" }
      ],
      "dry_run_result": {
        "is_success": true,
        "explain_plan": "Hash Left Join (cost=10.20..45.12)",
        "error_message": null
      },
      "ai_guide_report": "해당 테이블의 DDL을 분석하여 최적의 JOIN 구조로 변환했습니다."
    }
  ]
}
```
