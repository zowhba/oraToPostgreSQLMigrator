# AQMS (AI Query Migration System)

AI를 활용하여 Oracle MyBatis XML 쿼리를 PostgreSQL 환경으로 자동 변환해주는 통합 시스템입니다.

## 🏗️ 프로젝트 구조

- **backend/**: FastAPI 기반의 변환 엔진 가동 (Port 8000)
- **frontend/**: Vue/Vite 기반의 고성능 UI (Port 5173)
- **dev.sh**: 통합 로컬 개발 환경 실행 스크립트
- **build.sh**: 프런트엔드 정적 파일 빌드 스크립트
- **package.json**: 통합 태스크 오케스트레이션 (npm scripts)

## 🚀 실행 방법

### 1. 환경 설정
`.env` 파일을 프로젝트 루트에 생성하고 필요한 정보를 입력합니다. (단축 명령어: `cp .env.example .env`)

### 2. 통합 실행 (Backend + Frontend)
권장하는 실행 방법입니다.

```bash
# 실행 전 패키지 설치 및 동시 가동
./dev.sh

# 또는 npm 사용 시
npm run dev
```

### 3. 프런트엔드 빌드
```bash
./build.sh

# 또는 npm 사용 시
npm run build
```

## 🧪 테스트 실행
백엔드 로직의 정합성을 검증합니다.

```bash
python3 -m pytest backend/tests/

# 또는 npm 사용 시
npm test
```

## 🗄️ 데이터베이스 가이드
- **Application DB**: `sql_migrator_app` (프로젝트 정보 저장)
- **Target DB**: `sql_migrator_target` (Dry-run 검증용)
