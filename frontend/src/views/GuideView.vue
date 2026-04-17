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
          <div class="step-desc">LLM 자동 변환 (멀티모델)</div>
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
            <strong>원인:</strong> 테이블이 현재 검색 경로(search_path)에 없거나 실제 DB에 생성되지 않음<br>
            <strong>해결:</strong> 프로젝트 설정 → 스키마 필드에 올바른 스키마명 입력. 여러 스키마를 사용하는 경우 쉼표(<code>,</code>)로 구분하여 모두 입력할 수 있습니다. (예: <code>schema1, schema2</code>)
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
          <div class="error-code">syntax error at or near "xxx" (IN, UPPER 등)</div>
          <div class="error-solution">
            <strong>원인:</strong> MyBatis <code>&lt;foreach&gt;</code> 또는 <code>&lt;trim&gt;</code> 태그의 <code>open</code>, <code>prefix</code> 속성(예: <code>1 IN (</code>)이 누락됨<br>
            <strong>해결:</strong> 최신 버전에서 자동 개선됨. 수동 수정 시 괄호<code>(</code>의 짝이 맞는지, 키워드가 누락되지 않았는지 확인
          </div>
        </div>
        <div class="error-item">
          <div class="error-code">syntax error at or near ".." (...)</div>
          <div class="error-solution">
            <strong>원인:</strong> 쿼리가 너무 길어 AI가 응답 시 뒷부분을 <code>...</code>으로 생략함<br>
            <strong>해결:</strong> 쿼리를 작은 단위로 분리하거나, .env의 <code>LLM_MAX_TOKENS</code> 값을 상향 조정 (현재 4096 이상 권장)
          </div>
        </div>
        <div class="error-item">
          <div class="error-code">syntax error at or near "0" (0"&gt;)</div>
          <div class="error-solution">
            <strong>원인:</strong> MyBatis 태그 내 <code>test="val &gt; 0"</code> 등의 기호가 태그 제거 시 잔재로 남음<br>
            <strong>해결:</strong> 최신 버전에서 자동 조치됨. 수동 수정 시 <code>"&gt;</code> 등의 기호가 SQL에 포함되지 않도록 주의
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

    <!-- 시스템 프롬프트 우선순위 -->
    <section class="guide-section">
      <h2 class="section-title">📝 시스템 프롬프트 적용 우선순위</h2>
      <p class="section-desc">
        AI 변환 시 사용되는 시스템 프롬프트는 3단계 우선순위를 가집니다.
        상위 프롬프트가 설정되어 있으면 하위는 무시됩니다.
      </p>
      <div class="priority-list">
        <div class="priority-item priority-1">
          <div class="priority-rank">1순위</div>
          <div class="priority-content">
            <strong>1회성 시스템 프롬프트 (변환 화면)</strong>
            <p>변환 요청 시 "시스템 프롬프트 직접 입력" 영역에 작성한 프롬프트.<br>
            해당 요청에만 적용되며 저장되지 않습니다.</p>
          </div>
        </div>
        <div class="priority-arrow-down">▼</div>
        <div class="priority-item priority-2">
          <div class="priority-rank">2순위</div>
          <div class="priority-content">
            <strong>프로젝트별 시스템 프롬프트 (프로젝트 설정)</strong>
            <p>프로젝트 설정에서 입력한 프롬프트.<br>
            해당 프로젝트의 모든 변환에 적용됩니다. 프로젝트별 특성에 맞는 지침을 추가할 때 유용합니다.</p>
          </div>
        </div>
        <div class="priority-arrow-down">▼</div>
        <div class="priority-item priority-3">
          <div class="priority-rank">3순위</div>
          <div class="priority-content">
            <strong>전역 기본 시스템 프롬프트 (전역 설정)</strong>
            <p>전역 설정 > LLM 모델 설정에서 관리하는 기본 프롬프트.<br>
            위 두 가지가 모두 비어있을 때 사용됩니다.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 토큰 모니터링 & 과금 정책 -->
    <section class="guide-section">
      <h2 class="section-title">💰 토큰 사용량 모니터링 & 과금 정책</h2>

      <h3 class="sub-title">토큰 사용량 추적</h3>
      <p class="section-desc">
        모든 LLM 변환 요청에 대해 입력(Input) / 출력(Output) 토큰 사용량이 자동으로 기록됩니다.
      </p>
      <div class="token-guide-grid">
        <div class="token-guide-item">
          <div class="token-guide-icon">📄</div>
          <div>
            <strong>요청 단위</strong>
            <p>작업 히스토리의 각 시도(Attempt)마다 해당 배치의 총 입력/출력 토큰 수가 표시됩니다.</p>
          </div>
        </div>
        <div class="token-guide-item">
          <div class="token-guide-icon">📁</div>
          <div>
            <strong>프로젝트 단위</strong>
            <p>계층형 히스토리에서 프로젝트 헤더에 해당 프로젝트의 누적 토큰 사용량과 전체 예상 비용이 표시됩니다.</p>
          </div>
        </div>
        <div class="token-guide-item">
          <div class="token-guide-icon">💵</div>
          <div>
            <strong>비용 예측</strong>
            <p>각 요청의 사용 모델과 토큰 수를 기반으로 원화(KRW) 기준 예상 비용이 자동 계산됩니다.<br>
            <span class="field-tip">환율 기준: 1 USD = 1,450 KRW (고정)</span></p>
          </div>
        </div>
      </div>

      <h3 class="sub-title">과금 정책 관리</h3>
      <p class="section-desc">
        전역 설정 > LLM 모델 설정 하단의 <strong>모델별 과금 정책</strong> 테이블에서 각 모델의 토큰 단가를 조회하고 편집할 수 있습니다.
      </p>
      <div class="pricing-guide-table">
        <div class="pricing-guide-row header">
          <div>항목</div>
          <div>설명</div>
        </div>
        <div class="pricing-guide-row">
          <div><code>입력 ($/1M tokens)</code></div>
          <div>모델에 전송되는 프롬프트 + 컨텍스트의 100만 토큰당 USD 단가</div>
        </div>
        <div class="pricing-guide-row">
          <div><code>출력 ($/1M tokens)</code></div>
          <div>모델이 생성하는 응답의 100만 토큰당 USD 단가</div>
        </div>
      </div>
      <div class="info-box" style="margin-top: 16px;">
        <strong>💡 과금 단가가 변경되면:</strong> 전역 설정에서 단가를 수정하고 저장하세요. 이후 조회되는 히스토리의 예상 비용에 즉시 반영됩니다.
        기존 히스토리의 비용도 최신 단가로 재계산되어 표시됩니다.
      </div>
    </section>

    <!-- LLM 모델 관리 -->
    <section class="guide-section">
      <h2 class="section-title">🤖 LLM 모델 관리</h2>
      <p class="section-desc">
        여러 AI 모델을 지원하며, 용도에 맞게 선택하여 사용할 수 있습니다.
      </p>
      <div class="model-guide-grid">
        <div class="model-guide-card">
          <div class="model-guide-name">Claude 4.5 Haiku</div>
          <div class="model-guide-trait">가장 경제적</div>
          <p>빠른 속도와 합리적인 비용. 단순한 쿼리 변환에 적합합니다.</p>
        </div>
        <div class="model-guide-card">
          <div class="model-guide-name">Azure ChatGPT 5.2</div>
          <div class="model-guide-trait">안정적</div>
          <p>Azure 인프라 기반의 안정적인 성능. 기본 모델로 적합합니다.</p>
        </div>
        <div class="model-guide-card">
          <div class="model-guide-name">Claude 4.5 Sonnet</div>
          <div class="model-guide-trait">균형 (추천)</div>
          <p>성능과 비용의 최적 밸런스. 대부분의 변환 작업에 권장됩니다.</p>
        </div>
        <div class="model-guide-card">
          <div class="model-guide-name">Claude 4.6 Opus</div>
          <div class="model-guide-trait">최고 성능</div>
          <p>최강의 추론 성능. 복잡한 쿼리나 정밀한 변환이 필요할 때 사용합니다.</p>
        </div>
      </div>
      <div class="info-box" style="margin-top: 16px;">
        <strong>⚙️ 모델 전환:</strong> 전역 설정에서 활성 모델을 변경할 수 있습니다.
        Admin 모드에서는 사용 가능한 모델 목록을 제한할 수도 있습니다.
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

/* ─── 프롬프트 우선순위 ─── */
.priority-list {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
}

.priority-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 20px;
  border-radius: 10px;
  width: 100%;
}

.priority-1 {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border: 1px solid #93c5fd;
}

.priority-2 {
  background: linear-gradient(135deg, #f0fdf4, #dcfce7);
  border: 1px solid #86efac;
}

.priority-3 {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.priority-rank {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 6px;
  white-space: nowrap;
  flex-shrink: 0;
  margin-top: 2px;
}

.priority-content strong {
  font-size: 14px;
  color: #1e293b;
  display: block;
  margin-bottom: 4px;
}

.priority-content p {
  font-size: 13px;
  color: #64748b;
  margin: 0;
  line-height: 1.6;
}

.priority-arrow-down {
  color: #94a3b8;
  font-size: 16px;
  padding: 4px 0;
}

/* ─── 토큰 모니터링 가이드 ─── */
.token-guide-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 24px;
}

.token-guide-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 16px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.token-guide-icon {
  font-size: 22px;
  flex-shrink: 0;
  margin-top: 2px;
}

.token-guide-item strong {
  font-size: 14px;
  color: #1e293b;
  display: block;
  margin-bottom: 4px;
}

.token-guide-item p {
  font-size: 13px;
  color: #64748b;
  margin: 0;
  line-height: 1.6;
}

.pricing-guide-table {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
  font-size: 13px;
}

.pricing-guide-row {
  display: grid;
  grid-template-columns: 200px 1fr;
  border-bottom: 1px solid #e2e8f0;
}

.pricing-guide-row:last-child {
  border-bottom: none;
}

.pricing-guide-row > div {
  padding: 12px 16px;
  line-height: 1.5;
  color: #475569;
}

.pricing-guide-row > div:first-child {
  border-right: 1px solid #e2e8f0;
}

.pricing-guide-row.header {
  background: #f1f5f9;
  font-weight: 700;
  color: #374151;
}

.pricing-guide-row code {
  background: #e2e8f0;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #1e293b;
}

/* ─── LLM 모델 가이드 ─── */
.model-guide-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.model-guide-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px;
}

.model-guide-name {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 4px;
}

.model-guide-trait {
  font-size: 11px;
  font-weight: 600;
  color: #6366f1;
  background: #eef2ff;
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 8px;
}

.model-guide-card p {
  font-size: 12px;
  color: #64748b;
  margin: 0;
  line-height: 1.5;
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
