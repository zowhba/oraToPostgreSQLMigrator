# AI 쿼리 변환 시스템 - Frontend

Oracle → PostgreSQL 쿼리 자동 변환을 위한 Vue.js 기반 프론트엔드 애플리케이션입니다.

## 기술 스택

- **Framework**: Vue 3
- **Build Tool**: Vite
- **Language**: JavaScript
- **HTTP Client**: Axios

## 프로젝트 구조

```
sql_migrator_frontend/
├── src/
│   ├── api/
│   │   └── index.js          # API 호출 모듈 (Mock/실제 Backend 전환)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppHeader.vue     # 상단 헤더 (프로젝트 상태 표시)
│   │   │   └── AppSidebar.vue    # 좌측 사이드바 메뉴
│   │   └── convert/
│   │       ├── FileUpload.vue    # XML 파일 업로드
│   │       ├── QueryTable.vue    # 쿼리 목록 테이블
│   │       ├── QueryDetail.vue   # 쿼리 상세 (탭 구성)
│   │       ├── SqlCompare.vue    # SQL 비교 (라인별 diff)
│   │       ├── ConversionLog.vue # 변환 로그
│   │       ├── DryRunResult.vue  # Dry Run 결과
│   │       └── DifficultyBadge.vue # 난이도 배지
│   ├── views/
│   │   ├── SettingView.vue   # 프로젝트 설정 페이지
│   │   ├── ConvertView.vue   # 쿼리 변환 페이지
│   │   └── HistoryView.vue   # 작업 히스토리 페이지
│   ├── utils/
│   │   ├── xmlParser.js      # MyBatis XML 파싱
│   │   └── historyStorage.js # 히스토리 localStorage 관리
│   ├── App.vue               # 루트 컴포넌트
│   ├── main.js               # 앱 진입점
│   └── router.js             # 라우터 설정
├── vite.config.js            # Vite 설정 (프록시 포함)
├── package.json
└── README.md
```

## 설치 및 실행

```bash
# 의존성 설치
npm install

# 개발 서버 실행
npm run dev

# 프로덕션 빌드 (dist/ 폴더 생성)
npm run build
```

## 화면 구성

### 1. 프로젝트 설정 (`/setting`)

프로젝트 및 PostgreSQL 접속 정보를 관리합니다.

**기능:**
- 프로젝트 목록 조회
- 프로젝트 등록/수정/삭제
- DB 연결 테스트
- 프로젝트 선택/해제

### 2. 쿼리 변환 (`/convert`)

MyBatis XML 파일을 업로드하여 쿼리를 변환합니다.

**기능:**
- XML 파일 업로드 및 파싱
- 쿼리 변환 요청
- 변환 결과 확인 (난이도, SQL 비교, 변환 로그, Dry Run 결과)
- 결과 XML 다운로드
- 최근 작업 파일 빠른 접근

### 3. 작업 히스토리 (`/history`)

변환 작업 이력을 조회합니다.

**기능:**
- 히스토리 목록 조회
- 통계 요약 (난이도별, Dry Run 결과별)
- 히스토리 삭제
- 히스토리에서 변환 화면으로 이동

---

## API 연동 설정

### Mock 모드 (개발용)

기본적으로 Mock 모드가 활성화되어 있어 Backend 없이 프론트엔드를 개발할 수 있습니다.

```javascript
// src/api/index.js
const USE_MOCK = true  // Mock 모드 활성화
```

### Backend 연동 모드

실제 Backend와 연동하려면 다음 설정을 변경하세요.

#### 1단계: Mock 모드 비활성화

```javascript
// src/api/index.js
const USE_MOCK = false  // Mock 모드 비활성화
```

#### 2단계: Backend 서버 주소 설정

```javascript
// vite.config.js
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',  // Backend 서버 주소
        changeOrigin: true
      }
    }
  }
})
```

#### 3단계: Frontend 서버 재시작

```bash
# Ctrl+C로 기존 서버 종료 후
npm run dev
```

---

## Backend API 규격

### Interface A: 프로젝트 관리

| Method | Endpoint | 설명 |
|--------|----------|------|
| `POST` | `/api/projects` | 프로젝트 등록 |
| `GET` | `/api/projects` | 프로젝트 목록 조회 |
| `GET` | `/api/projects/{project_id}` | 단일 프로젝트 조회 |
| `DELETE` | `/api/projects/{project_id}` | 프로젝트 삭제 |
| `POST` | `/api/projects/{project_id}/test-connection` | DB 연결 테스트 |

#### 프로젝트 등록 요청 예시

```json
POST /api/projects
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

#### 프로젝트 등록 응답 예시

```json
{
  "status": "success",
  "message": "프로젝트 DB 설정이 완료되었습니다.",
  "project_id": "PRJ_SKB_001"
}
```

#### 프로젝트 목록 조회 응답 예시

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

#### 단일 프로젝트 조회 응답 예시 (비밀번호 마스킹)

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

#### DB 연결 테스트 응답 예시

```json
{
  "status": "success",
  "message": "DB 연결 성공",
  "connected": true
}
```

### Interface B: 쿼리 변환

| Method | Endpoint | 설명 |
|--------|----------|------|
| `POST` | `/api/convert` | 쿼리 변환 요청 |

#### 쿼리 변환 요청 예시

```json
POST /api/convert
{
  "project_id": "PRJ_SKB_001",
  "xml_file_name": "UserMapper.xml",
  "mapper_namespace": "com.example.UserMapper",
  "file_created_at": "2026-03-13 15:00:00",
  "queries": [
    {
      "query_id": "selectUser",
      "tag_name": "select",
      "attributes": {
        "parameterType": "map",
        "resultType": "User"
      },
      "original_sql_xml": "<select id=\"selectUser\">SELECT NVL(name, 'N/A') FROM users WHERE created_at > SYSDATE</select>"
    }
  ]
}
```

#### 쿼리 변환 응답 예시

```json
{
  "project_id": "PRJ_SKB_001",
  "queries": [
    {
      "query_id": "selectUser",
      "tag_name": "select",
      "attributes": {
        "parameterType": "map",
        "resultType": "User"
      },
      "original_sql_xml": "<select id=\"selectUser\">SELECT NVL(name, 'N/A') FROM users WHERE created_at > SYSDATE</select>",
      "difficulty_level": 1,
      "converted_sql": "<select id=\"selectUser\">SELECT COALESCE(name, 'N/A') FROM users WHERE created_at > CURRENT_TIMESTAMP</select>",
      "conversion_log": [
        { "category": "FUNCTION", "before": "NVL", "after": "COALESCE" },
        { "category": "FUNCTION", "before": "SYSDATE", "after": "CURRENT_TIMESTAMP" }
      ],
      "dry_run_result": {
        "is_success": true,
        "explain_plan": "Seq Scan on users (cost=0.00..35.50 rows=10 width=32)",
        "error_message": null
      },
      "ai_guide_report": "NVL 함수를 COALESCE로, SYSDATE를 CURRENT_TIMESTAMP로 변환했습니다."
    }
  ]
}
```

---

## 데이터 구조

### 난이도 레벨 (difficulty_level)

| 레벨 | 설명 | 색상 |
|------|------|------|
| 1 | 완전 자동 변환 | 초록 |
| 2 | AI 보정 필요 | 주황 |
| 3 | 전문가 수동 검토 | 빨강 |

### 변환 로그 카테고리 (conversion_log.category)

- `JOIN`: 조인 문법 변환
- `FUNCTION`: 함수 변환
- `SYNTAX`: 문법 변환
- `HINT`: 힌트 변환
- `DATATYPE`: 데이터 타입 변환

---

## 로컬 스토리지 사용

| Key | 용도 |
|-----|------|
| `currentProject` | 현재 선택된 프로젝트 정보 |
| `sql_migrator_mock_projects` | Mock 모드 프로젝트 데이터 |
| `sql_migrator_history` | 변환 작업 히스토리 |

### 초기화 방법

```javascript
// 브라우저 개발자 도구 Console에서 실행
localStorage.clear()  // 전체 초기화

// 또는 개별 초기화
localStorage.removeItem('currentProject')
localStorage.removeItem('sql_migrator_mock_projects')
localStorage.removeItem('sql_migrator_history')
```

---

## 트러블슈팅

### Backend 연결 실패 시

1. Backend 서버가 실행 중인지 확인
2. `vite.config.js`의 proxy target 주소 확인
3. CORS 설정 확인 (Backend에서 설정 필요할 수 있음)
4. 브라우저 개발자 도구 Network 탭에서 요청/응답 확인

### Mock 모드로 되돌리기

```javascript
// src/api/index.js
const USE_MOCK = true
```

---

## 참고 문서

- [AI 쿼리 변환 시스템 연동 규격서 v1.8](../sql_migrator/AI_Query_Migration_Spec_v1.7_수정버전.md)
