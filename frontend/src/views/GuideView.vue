<template>
  <div class="guide-view">
    <!-- 헤더 -->
    <div class="guide-header">
      <div class="header-badge">📖 사용 가이드</div>
      <h1 class="guide-title">Oracle → PostgreSQL<br>SQL 마이그레이터</h1>
      <p class="guide-subtitle">
        MyBatis XML 기반 Oracle SQL을 PostgreSQL 호환 SQL로 자동 변환하고,<br>
        실제 DB 환경에서 안전하게 검증하는 AI 마이그레이션 도구입니다.
      </p>
    </div>

    <!-- 전체 파이프라인 -->
    <section class="guide-section">
      <h2 class="section-title">⚙️ 전체 처리 파이프라인</h2>
      <div class="pipeline">
        <div class="pipeline-step">
          <div class="step-num">1</div>
          <div class="step-icon">📂</div>
          <div class="step-label">XML 업로드</div>
          <div class="step-desc">MyBatis Mapper XML 파일</div>
        </div>
        <div class="pipeline-arrow">→</div>
        <div class="pipeline-step">
          <div class="step-num">2</div>
          <div class="step-icon">🔍</div>
          <div class="step-label">SQL 파싱</div>
          <div class="step-desc">쿼리 추출 &amp; 난이도 분류</div>
        </div>
        <div class="pipeline-arrow">→</div>
        <div class="pipeline-step">
          <div class="step-num">3</div>
          <div class="step-icon">🤖</div>
          <div class="step-label">AI 변환</div>
          <div class="step-desc">Azure OpenAI GPT 자동 변환</div>
        </div>
        <div class="pipeline-arrow">→</div>
        <div class="pipeline-step">
          <div class="step-num">4</div>
          <div class="step-icon">🧪</div>
          <div class="step-label">Dry-run</div>
          <div class="step-desc">PostgreSQL EXPLAIN 검증</div>
        </div>
        <div class="pipeline-arrow">→</div>
        <div class="pipeline-step">
          <div class="step-num">5</div>
          <div class="step-icon">📥</div>
          <div class="step-label">결과 다운로드</div>
          <div class="step-desc">XML / Excel 내보내기</div>
        </div>
      </div>
    </section>

    <!-- 난이도 분류 -->
    <section class="guide-section">
      <h2 class="section-title">📊 쿼리 난이도 분류 기준</h2>
      <div class="card-grid">
        <div class="level-card level-1">
          <div class="level-badge">Lv.1</div>
          <h3>단순</h3>
          <ul>
            <li>단일 테이블 SELECT/INSERT/UPDATE/DELETE</li>
            <li>간단한 WHERE 조건</li>
            <li>기본 집계함수 (COUNT, SUM 등)</li>
            <li>MyBatis 동적 태그 미사용</li>
          </ul>
        </div>
        <div class="level-card level-2">
          <div class="level-badge">Lv.2</div>
          <h3>중간</h3>
          <ul>
            <li>다중 테이블 JOIN (2~3개)</li>
            <li>서브쿼리 사용</li>
            <li>MyBatis &lt;if&gt;, &lt;where&gt;, &lt;foreach&gt; 태그</li>
            <li>Oracle 함수 변환 필요 (NVL → COALESCE 등)</li>
          </ul>
        </div>
        <div class="level-card level-3">
          <div class="level-badge">Lv.3</div>
          <h3>복잡</h3>
          <ul>
            <li>복잡한 다중 JOIN 또는 중첩 서브쿼리</li>
            <li>Oracle 전용 문법 (CONNECT BY, ROWNUM 등)</li>
            <li>MyBatis &lt;choose&gt;/&lt;when&gt; 복합 동적 쿼리</li>
            <li>MERGE, WITH(CTE), 분석함수 사용</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- Dry-run 정책 -->
    <section class="guide-section">
      <h2 class="section-title">🧪 Dry-run 작동 방식 및 안전 정책</h2>

      <div class="highlight-box">
        <div class="highlight-icon">🛡️</div>
        <div>
          <strong>Dry-run은 실제 데이터를 변경하지 않습니다.</strong><br>
          SELECT, INSERT, UPDATE, DELETE 모두 <code>EXPLAIN</code>으로만 실행되어 실행 계획 분석만 수행합니다.
        </div>
      </div>

      <h3 class="sub-title">EXPLAIN 방식의 원리</h3>
      <div class="code-block">
        <div class="code-comment">-- PostgreSQL에 실제로 실행되는 명령어</div>
        <div class="code-line"><span class="kw">EXPLAIN</span> SELECT ... FROM table WHERE ...</div>
        <div class="code-line"><span class="kw">EXPLAIN</span> INSERT INTO table VALUES (...)</div>
        <div class="code-line"><span class="kw">EXPLAIN</span> UPDATE table SET col = val WHERE ...</div>
        <div class="code-line"><span class="kw">EXPLAIN</span> DELETE FROM table WHERE ...</div>
        <div class="code-comment mt">-- ↑ EXPLAIN은 실행 계획만 분석하며 데이터를 건드리지 않습니다</div>
      </div>

      <h3 class="sub-title">2중 안전 장치</h3>
      <div class="safety-grid">
        <div class="safety-item">
          <div class="safety-icon">①</div>
          <div>
            <strong>EXPLAIN only</strong><br>
            <span class="desc">실제 SQL이 아닌 EXPLAIN 명령만 전달. SQL 실행 자체가 일어나지 않음</span>
          </div>
        </div>
        <div class="safety-item">
          <div class="safety-icon">②</div>
          <div>
            <strong>트랜잭션 자동 롤백</strong><br>
            <span class="desc">autocommit=False + 성공/실패 모두 rollback() 호출. 예외적으로 DB 변경이 발생해도 원복 보장</span>
          </div>
        </div>
        <div class="safety-item">
          <div class="safety-icon">③</div>
          <div>
            <strong>Statement Timeout</strong><br>
            <span class="desc">기본 5초 타임아웃으로 DB에 과부하 방지 (.env의 DRYRUN_STATEMENT_TIMEOUT_MS 설정)</span>
          </div>
        </div>
      </div>

      <div class="info-box">
        <strong>⚠️ EXPLAIN의 한계:</strong> 문법 오류, 테이블/컬럼 존재 여부, JOIN 유효성은 검증하지만,
        유니크 키 충돌·FK 제약 위반 등 <em>런타임 데이터 의존 오류</em>는 잡아낼 수 없습니다.
        이는 EXPLAIN ANALYZE가 아닌 EXPLAIN을 쓰는 데 따른 의도적 트레이드오프입니다.
      </div>
    </section>

    <!-- MyBatis 태그 처리 -->
    <section class="guide-section">
      <h2 class="section-title">🏷️ MyBatis XML 태그 처리 정책</h2>
      <p class="section-desc">
        Dry-run 전 MyBatis XML을 순수 SQL로 변환하는 단계에서 다음 규칙을 적용합니다.
      </p>

      <div class="tag-table">
        <div class="tag-row header">
          <div>MyBatis 태그 / 구문</div>
          <div>처리 방식</div>
          <div>예시</div>
        </div>
        <div class="tag-row">
          <div><code>&lt;![CDATA[ ... ]]&gt;</code></div>
          <div>내부 SQL 텍스트 추출</div>
          <div><code>&lt;![CDATA[ SELECT ... ]]&gt;</code> → <code>SELECT ...</code></div>
        </div>
        <div class="tag-row">
          <div><code>-- SQL 주석</code></div>
          <div>줄 압축 전 제거 <span class="warn-badge">중요</span></div>
          <div><code>-- col\nFROM t</code> → <code>FROM t</code> (주석이 FROM을 삼키지 않도록)</div>
        </div>
        <div class="tag-row">
          <div><code>/* 블록 주석 */</code></div>
          <div>제거</div>
          <div><code>/* hint */</code> → 공백</div>
        </div>
        <div class="tag-row">
          <div><code>&lt;where&gt;</code></div>
          <div><code>WHERE</code> 키워드로 치환</div>
          <div>첫 AND/OR 자동 제거</div>
        </div>
        <div class="tag-row">
          <div><code>&lt;if&gt;</code>, <code>&lt;foreach&gt;</code></div>
          <div>태그 제거, 내부 SQL 보존</div>
          <div>조건 분기 없이 모든 SQL 포함</div>
        </div>
        <div class="tag-row">
          <div><code>&lt;choose&gt;&lt;when&gt;</code></div>
          <div>첫 번째 &lt;when&gt; 브랜치만 선택</div>
          <div>대표 케이스로 실행 계획 분석</div>
        </div>
        <div class="tag-row">
          <div><code>#{param}</code></div>
          <div><code>NULL</code>로 치환</div>
          <div><code>WHERE id = #{id}</code> → <code>WHERE id = NULL</code></div>
        </div>
        <div class="tag-row">
          <div><code>${param}</code></div>
          <div><code>1</code>로 치환</div>
          <div>동적 테이블명 등에 사용되는 경우</div>
        </div>
        <div class="tag-row">
          <div>SQL 비교 연산자 <code>&lt;=</code> <code>&gt;=</code> <code>&lt;&gt;</code></div>
          <div>보호 후 복원</div>
          <div>XML 태그로 오인되지 않도록 플레이스홀더 처리</div>
        </div>
      </div>
    </section>

    <!-- 프로젝트 설정 -->
    <section class="guide-section">
      <h2 class="section-title">🔧 프로젝트 설정 가이드</h2>
      <div class="setup-steps">
        <div class="setup-step">
          <div class="setup-num">1</div>
          <div class="setup-content">
            <strong>프로젝트 등록</strong>
            <p>설정 메뉴 → 새 프로젝트 → 프로젝트 ID와 이름 입력</p>
          </div>
        </div>
        <div class="setup-step">
          <div class="setup-num">2</div>
          <div class="setup-content">
            <strong>PostgreSQL 접속 정보 입력</strong>
            <p>변환된 SQL을 검증할 대상 PostgreSQL DB 정보 입력<br>
            <span class="field-tip">Host / Port / Database 이름 / 스키마(선택) / 사용자 / 비밀번호</span></p>
          </div>
        </div>
        <div class="setup-step">
          <div class="setup-num">3</div>
          <div class="setup-content">
            <strong>스키마 설정 (중요)</strong>
            <p>테이블이 <code>public</code>이 아닌 별도 스키마(예: <code>edmp</code>)에 있으면<br>
            스키마 필드에 반드시 입력하세요. 미입력 시 "테이블 없음" 에러 발생</p>
          </div>
        </div>
        <div class="setup-step">
          <div class="setup-num">4</div>
          <div class="setup-content">
            <strong>DB 연결 테스트 후 저장</strong>
            <p>저장 전 "DB 연결 테스트" 버튼으로 접속 확인 권장</p>
          </div>
        </div>
        <div class="setup-step">
          <div class="setup-num">5</div>
          <div class="setup-content">
            <strong>프로젝트 사용 설정</strong>
            <p>"이 프로젝트 사용하기" 버튼 클릭 → 헤더에 사용 중 프로젝트 표시됨</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 에러 해결 가이드 -->
    <section class="guide-section">
      <h2 class="section-title">🚨 자주 발생하는 Dry-run 에러 해결</h2>
      <div class="error-list">
        <div class="error-item">
          <div class="error-code">relation "xxx" does not exist</div>
          <div class="error-solution">
            <strong>원인:</strong> 테이블이 해당 스키마에 없거나 스키마 설정 누락<br>
            <strong>해결:</strong> 프로젝트 설정 → 스키마 필드에 올바른 스키마명 입력 (예: edmp)
          </div>
        </div>
        <div class="error-item">
          <div class="error-code">missing FROM-clause entry for table "xxx"</div>
          <div class="error-solution">
            <strong>원인:</strong> 원본 XML에 <code>-- SQL 주석</code>이 있고, 한 줄로 압축될 때 FROM 절이 삭제됨 (자동 처리됨)<br>
            <strong>해결:</strong> 최신 버전에서 자동 처리. 재시도해도 동일하면 SQL 내 <code>--</code> 주석 확인
          </div>
        </div>
        <div class="error-item">
          <div class="error-code">function "xxx" does not exist</div>
          <div class="error-solution">
            <strong>원인:</strong> Oracle 전용 함수가 아직 PostgreSQL로 변환되지 않음 (NVL, DECODE 등)<br>
            <strong>해결:</strong> AI 변환 탭에서 수동으로 SQL을 수정하거나 재변환 요청
          </div>
        </div>
        <div class="error-item">
          <div class="error-code">syntax error at or near "xxx"</div>
          <div class="error-solution">
            <strong>원인:</strong> Oracle 전용 문법(ROWNUM, CONNECT BY, START WITH 등) 잔존<br>
            <strong>해결:</strong> 변환된 SQL을 직접 수정. ROWNUM → LIMIT, CONNECT BY → recursive CTE
          </div>
        </div>
        <div class="error-item">
          <div class="error-code">지원하지 않는 SQL 문 유형</div>
          <div class="error-solution">
            <strong>원인:</strong> &lt;![CDATA[...]]&gt; 처리 후 SELECT/INSERT/UPDATE/DELETE로 시작하지 않는 경우<br>
            <strong>해결:</strong> 원본 XML 확인. DDL(CREATE, ALTER 등)은 Dry-run 대상이 아님
          </div>
        </div>
      </div>
    </section>

    <!-- 푸터 -->
    <div class="guide-footer">
      <p>Made with ❤️ by SQL Migrator Team · Oracle to PostgreSQL Migration Tool</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'GuideView'
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

.guide-view {
  max-width: 900px;
  font-family: 'Inter', sans-serif;
  padding-bottom: 60px;
}

/* ─── 헤더 ─── */
.guide-header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  border-radius: 16px;
  padding: 48px 40px;
  margin-bottom: 32px;
  text-align: center;
  position: relative;
  overflow: hidden;
}

.guide-header::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle at 60% 40%, rgba(102,126,234,0.15) 0%, transparent 60%);
  pointer-events: none;
}

.header-badge {
  display: inline-block;
  background: rgba(102,126,234,0.25);
  border: 1px solid rgba(102,126,234,0.5);
  color: #a5b4fc;
  font-size: 13px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 20px;
  margin-bottom: 20px;
  letter-spacing: 0.5px;
}

.guide-title {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 16px;
  line-height: 1.3;
}

.guide-subtitle {
  font-size: 15px;
  color: #94a3b8;
  line-height: 1.8;
  margin: 0;
}

/* ─── 섹션 공통 ─── */
.guide-section {
  background: #fff;
  border-radius: 12px;
  padding: 32px;
  margin-bottom: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 20px;
  padding-bottom: 12px;
  border-bottom: 2px solid #f1f5f9;
}

.section-desc {
  color: #64748b;
  margin: -8px 0 20px;
  font-size: 14px;
}

.sub-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin: 24px 0 12px;
}

/* ─── 파이프라인 ─── */
.pipeline {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  flex-wrap: wrap;
  gap: 8px;
}

.pipeline-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 20px;
  min-width: 110px;
  position: relative;
}

.step-num {
  position: absolute;
  top: -10px;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  font-size: 11px;
  font-weight: 700;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-icon {
  font-size: 24px;
  margin-top: 4px;
}

.step-label {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.step-desc {
  font-size: 11px;
  color: #64748b;
  text-align: center;
}

.pipeline-arrow {
  font-size: 20px;
  color: #cbd5e1;
  flex-shrink: 0;
}

/* ─── 난이도 카드 ─── */
.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.level-card {
  border-radius: 12px;
  padding: 20px;
  position: relative;
}

.level-card.level-1 {
  background: linear-gradient(135deg, #f0fdf4, #dcfce7);
  border: 1px solid #86efac;
}

.level-card.level-2 {
  background: linear-gradient(135deg, #fffbeb, #fef3c7);
  border: 1px solid #fcd34d;
}

.level-card.level-3 {
  background: linear-gradient(135deg, #fef2f2, #fee2e2);
  border: 1px solid #fca5a5;
}

.level-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 10px;
  margin-bottom: 10px;
}

.level-1 .level-badge { background: #16a34a; color: white; }
.level-2 .level-badge { background: #d97706; color: white; }
.level-3 .level-badge { background: #dc2626; color: white; }

.level-card h3 {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 12px;
}

.level-card ul {
  margin: 0;
  padding-left: 16px;
  font-size: 12px;
  color: #475569;
  line-height: 1.8;
}

/* ─── Dry-run 섹션 ─── */
.highlight-box {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border: 1px solid #93c5fd;
  border-radius: 10px;
  padding: 16px 20px;
  margin-bottom: 20px;
  font-size: 14px;
  color: #1e40af;
  line-height: 1.6;
}

.highlight-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.code-block {
  background: #0f172a;
  border-radius: 10px;
  padding: 20px 24px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.8;
  margin-bottom: 20px;
}

.code-comment {
  color: #64748b;
}

.code-comment.mt {
  margin-top: 8px;
}

.code-line {
  color: #e2e8f0;
}

.code-line .kw {
  color: #7dd3fc;
  font-weight: 600;
}

.safety-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.safety-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 16px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.safety-icon {
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.safety-item strong {
  font-size: 14px;
  color: #1e293b;
  display: block;
  margin-bottom: 2px;
}

.safety-item .desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.info-box {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 14px 16px;
  font-size: 13px;
  color: #92400e;
  line-height: 1.6;
}

.info-box em {
  font-style: normal;
  font-weight: 600;
}

/* ─── 태그 테이블 ─── */
.tag-table {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
  font-size: 13px;
}

.tag-row {
  display: grid;
  grid-template-columns: 1fr 1fr 2fr;
  gap: 0;
  border-bottom: 1px solid #e2e8f0;
}

.tag-row:last-child {
  border-bottom: none;
}

.tag-row > div {
  padding: 12px 16px;
  border-right: 1px solid #e2e8f0;
  line-height: 1.5;
}

.tag-row > div:last-child {
  border-right: none;
}

.tag-row.header {
  background: #f1f5f9;
  font-weight: 700;
  color: #374151;
}

.tag-row:not(.header) {
  color: #475569;
}

.tag-row:not(.header):hover {
  background: #f8fafc;
}

.tag-row code {
  background: #e2e8f0;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #1e293b;
}

.warn-badge {
  display: inline-block;
  background: #dc2626;
  color: white;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 4px;
}

/* ─── 설정 가이드 ─── */
.setup-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.setup-step {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 0;
  border-bottom: 1px dashed #e2e8f0;
  position: relative;
}

.setup-step:last-child {
  border-bottom: none;
}

.setup-num {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}

.setup-content strong {
  font-size: 14px;
  color: #1e293b;
  display: block;
  margin-bottom: 4px;
}

.setup-content p {
  font-size: 13px;
  color: #64748b;
  margin: 0;
  line-height: 1.6;
}

.setup-content code {
  background: #e2e8f0;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #1e293b;
}

.field-tip {
  font-size: 12px;
  color: #6366f1;
  background: #eef2ff;
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-block;
  margin-top: 4px;
}

/* ─── 에러 목록 ─── */
.error-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.error-item {
  border: 1px solid #fecaca;
  border-radius: 8px;
  overflow: hidden;
}

.error-code {
  background: #fef2f2;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #991b1b;
  font-weight: 600;
  padding: 10px 16px;
  border-bottom: 1px solid #fecaca;
}

.error-solution {
  padding: 12px 16px;
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
  background: white;
}

.error-solution strong {
  color: #1e293b;
}

.error-solution code {
  background: #e2e8f0;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #1e293b;
}

/* ─── 푸터 ─── */
.guide-footer {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}

/* ─── 반응형 ─── */
@media (max-width: 700px) {
  .card-grid {
    grid-template-columns: 1fr;
  }

  .pipeline {
    flex-direction: column;
  }

  .pipeline-arrow {
    transform: rotate(90deg);
  }

  .tag-row {
    grid-template-columns: 1fr;
  }

  .tag-row > div {
    border-right: none;
    border-bottom: 1px solid #e2e8f0;
  }
}
</style>
