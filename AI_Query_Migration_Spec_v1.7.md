# 📋 AI 쿼리 변환 시스템 최종 통합 연동 규격서 (v1.8)

본 규격서는 **AI 기반 Oracle → PostgreSQL 쿼리 변환 자동화 시스템**의 Frontend(고급)와 Backend(특급) 간의 효율적인 병렬 개발을 위해 데이터 구조와 통신 샘플을 인터페이스별로 명확히 정의합니다.

---

## 1. 프로젝트 개요
- **목적**: AI를 활용한 Oracle MyBatis 쿼리의 PostgreSQL 자동 변환 및 검증. [cite: 5, 6]
- **주요 전략**: 지능형 3단계 분류, DDL 스키마 인지, Dry Run 실시간 검증. [cite: 7, 39, 48]
- **담당자**: OSS서비스2팀 오지웅, 박세희. [cite: 12]

---

## 2. [Interface A] 프로젝트-DB 매핑 설정 (관리용)
사용자가 프로젝트를 생성·조회·삭제하고, 해당 프로젝트가 사용할 대상 PostgreSQL 접속 정보를 등록 및 연결 테스트합니다.

### 2.1. 엔드포인트 목록
| Method | Path | 설명 |
| :--- | :--- | :--- |
| `POST` | `/api/projects` | 프로젝트 + DB 접속정보 등록 |
| `GET` | `/api/projects` | 등록된 프로젝트 목록 조회 |
| `GET` | `/api/projects/{project_id}` | 단일 프로젝트 조회 (비밀번호 마스킹) |
| `DELETE` | `/api/projects/{project_id}` | 프로젝트 삭제 |
| `POST` | `/api/projects/{project_id}/test-connection` | DB 연결 테스트 |

### 2.2. Payload 규격

#### **(가) 프로젝트 등록 요청**
| 필드명 | 타입 | 필수 | 설명 |
| :--- | :--- | :---: | :--- |
| **`project_id`** | String | Y | 프로젝트 고유 ID (예: `PRJ_SKB_001`) |
| **`project_name`** | String | Y | 프로젝트 명칭 |
| **`db_config`** | Object | Y | 접속 정보 (`host`, `port`, `db_name`, `user`, `pw`) |

#### **(나) 프로젝트 목록 조회 응답**
| 필드명 | 타입 | 설명 |
| :--- | :--- | :--- |
| **`status`** | String | `success` |
| **`projects`** | Array | 프로젝트 요약 목록 (`project_id`, `project_name`, `db_config_summary`) |

#### **(다) DB 연결 테스트 응답**
| 필드명 | 타입 | 설명 |
| :--- | :--- | :--- |
| **`status`** | String | `success` \| `error` |
| **`message`** | String | 연결 결과 메시지 |
| **`connected`** | Boolean | 연결 성공 여부 |

### 2.3. 통신 샘플 (Interface A)

#### ① 프로젝트 등록 — `POST /api/projects`
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
**[Response: 200 OK]**
```json
{
  "status": "success",
  "message": "프로젝트 DB 설정이 완료되었습니다.",
  "project_id": "PRJ_SKB_001"
}
```
**[Response: 409 Conflict — 중복 ID]**
```json
{
  "detail": "프로젝트 ID 'PRJ_SKB_001'가 이미 존재합니다."
}
```

#### ② 프로젝트 목록 조회 — `GET /api/projects`
**[Response]**
```json
{
  "status": "success",
  "projects": [
    {
      "project_id": "PRJ_SKB_001",
      "project_name": "SKB 차세대 마이그레이션",
      "db_config_summary": "10.1.2.3:5432/target_pg_db (user=migrator)"
    }
  ]
}
```

#### ③ 단일 프로젝트 조회 — `GET /api/projects/{project_id}`
**[Response: 200 OK]** *(비밀번호는 `****`로 마스킹)*
```json
{
  "status": "success",
  "project_id": "PRJ_SKB_001",
  "project_name": "SKB 차세대 마이그레이션",
  "db_config": {
    "host": "10.1.2.3",
    "port": 5432,
    "db_name": "target_pg_db",
    "user": "migrator",
    "pw": "****"
  }
}
```
**[Response: 404 Not Found]**
```json
{
  "detail": "프로젝트 'PRJ_INVALID'를 찾을 수 없습니다."
}
```

#### ④ 프로젝트 삭제 — `DELETE /api/projects/{project_id}`
**[Response: 200 OK]**
```json
{
  "status": "success",
  "message": "프로젝트 'PRJ_SKB_001'가 삭제되었습니다."
}
```

#### ⑤ DB 연결 테스트 — `POST /api/projects/{project_id}/test-connection`
**[Response: 200 OK]**
```json
{
  "status": "success",
  "message": "DB 연결 성공 (10.1.2.3:5432/target_pg_db (user=migrator))",
  "connected": true
}
```
**[Response: 400 Bad Request — 연결 실패]**
```json
{
  "detail": "DB 연결 실패: could not connect to server: Connection refused"
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
| **`mapper_namespace`** | String | N | 원본 XML의 `<mapper namespace="...">` 값 (`.sql`/엑셀은 파일명으로 대체, 기본값 `""`) |
| **`file_created_at`** | String | Y | 요청 생성 일시 (`YYYY-MM-DD HH:mm:ss`) |
| **`source_type`** | String | N | 원본 파일 종류 — `xml`(기본값) \| `excel` \| `sql`. `sql`인 경우 Dry-run을 수행하지 않음 |

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
- **`is_skipped`**: Boolean (Dry-run을 아예 수행하지 않은 경우 `true`. **실패와 구분되며 난이도 분류 시그널에서 제외됨**)
- **`skip_reason`**: String (Dry-run을 생략한 사유)
- **`explain_plan`**: String (성공 시 PostgreSQL 실행 계획) [cite: 49]
- **`error_message`**: String (실패 시 DB 에러 메시지) [cite: 49]

### 3.3. `.sql` 스크립트 소스 처리 규칙 (`source_type = "sql"`)
프로시저·함수·패키지 등이 담긴 순수 SQL 스크립트를 입력으로 받을 때의 예외 규칙입니다.

| 단계 | XML/엑셀 소스 | `.sql` 소스 |
| :--- | :--- | :--- |
| 파일 파싱 | MyBatis 태그 단위 | 문장/오브젝트 단위 (단독 `/` 라인, 문자열·주석 인식 `;` 분할) |
| `query_id` | MyBatis SQL ID | 오브젝트명 (없으면 `NNN_앞단어` 형식) |
| `tag_name` | select/insert/update/delete | procedure / function / package_body / trigger / table / … |
| `original_sql_xml` | XML 조각 | **XML 래핑 없는 순수 SQL 원문** |
| DDL 스키마 조회 | 수행 | **수행 (변환 참고용으로 동일하게 사용)** |
| LLM 변환 프롬프트 | MyBatis 동적 태그 보존 규칙 | **PL/SQL → PL/pgSQL 변환 규칙** |
| Dry-run (EXPLAIN) | 수행 | **미수행** (`is_skipped = true`) |
| 난이도 분류 | Dry-run + LLM 시그널 | **LLM 시그널만** 사용 |
| 결과 다운로드 | `_postgresql.xml` / `.xlsx` | `_postgresql.sql` |

> **Dry-run을 생략하는 이유**: `CREATE OR REPLACE PROCEDURE` 등의 DDL은 `EXPLAIN` 대상이 아니며,
> 실제로 실행하면 대상 DB에 오브젝트가 생성되어 검증이 아닌 반영이 되어 버립니다.

**[Request 샘플: `.sql` 소스]**
```json
{
  "project_id": "PRJ_SKB_001",
  "xml_file_name": "SP_DM_DVC_UPD_FLAG_SET.sql",
  "mapper_namespace": "",
  "file_created_at": "2026-08-04 15:00:00",
  "source_type": "sql",
  "queries": [
    {
      "query_id": "SP_DM_DVC_UPD_FLAG_SET",
      "tag_name": "procedure",
      "attributes": { "objectType": "procedure" },
      "original_sql_xml": "CREATE OR REPLACE PROCEDURE SP_DM_DVC_UPD_FLAG_SET(...) IS BEGIN ... END;"
    }
  ]
}
```

**[Response 샘플: `dry_run_result`]**
```json
{
  "is_success": false,
  "is_skipped": true,
  "skip_reason": ".sql 스크립트 소스는 Dry-run을 수행하지 않습니다.",
  "executed_sql": null,
  "explain_plan": null,
  "error_message": null,
  "error_hint": "📌 **Dry-run 미수행**: ..."
}
```

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
