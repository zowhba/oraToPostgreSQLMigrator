"""
PL/SQL 전용 변환 보정 (AQMS).

설계 원칙
---------
1. **완전 분리**: 진입점은 `is_plsql_source()` 단 하나. False면 이 모듈의 어떤 코드도 돌지 않는다.
   기존 XML(MyBatis) / Excel / 순수 SQL 경로는 바이트 단위로 무영향.
2. **LLM에 맡기지 않는다**: 3대 위반은 결정론적으로 검출·보정한다.
   프롬프트 지시는 보조일 뿐이고, 최종 보증은 이 모듈이 한다.
3. **보정은 주석을 남긴다**: 사람이 이관 검토할 때 무엇이 왜 바뀌었는지 보여야 한다.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

# ── 소스 판별 ────────────────────────────────────────────────────────────────
_PLSQL_DDL = re.compile(
    r'\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:DEFINER\s*=\s*\S+\s+)?'
    r'(PROCEDURE|FUNCTION|PACKAGE(?:\s+BODY)?|TRIGGER)\b', re.I)
_ANON_BLOCK = re.compile(r'^\s*(DECLARE|BEGIN)\b.*?\bEND\s*;?\s*$', re.I | re.S)


def is_plsql_source(sql: str) -> bool:
    """PL/SQL 블록이면 True. 단문 SELECT/INSERT/UPDATE/MERGE 등은 항상 False."""
    if not sql or not sql.strip():
        return False
    stripped = _strip_comments_for_scan(sql)
    if _PLSQL_DDL.search(stripped):
        return True
    if _ANON_BLOCK.match(stripped.strip()):
        # DECLARE/BEGIN 으로 열고 END 로 닫는 익명 블록
        return bool(re.search(r'\bBEGIN\b', stripped, re.I))
    return False


# ── 주석 스캐너 (문자열 리터럴 회피) ────────────────────────────────────────
@dataclass
class Comment:
    start: int
    end: int
    text: str
    kind: str  # 'line' | 'block'


def scan_comments(sql: str) -> list[Comment]:
    out, i, n = [], 0, len(sql)
    while i < n:
        c = sql[i]
        if c in "'\"":
            q, i = c, i + 1
            while i < n:
                if sql[i] == q:
                    if q == "'" and i + 1 < n and sql[i + 1] == "'":
                        i += 2; continue
                    break
                i += 1
            i += 1; continue
        if sql.startswith('--', i):
            j = sql.find('\n', i); j = n if j < 0 else j
            out.append(Comment(i, j, sql[i:j], 'line')); i = j; continue
        if sql.startswith('/*', i):
            j = sql.find('*/', i + 2); j = n if j < 0 else j + 2
            out.append(Comment(i, j, sql[i:j], 'block')); i = j; continue
        i += 1
    return out


def _strip_comments_for_scan(sql: str) -> str:
    """판별용으로만 주석을 공백으로 치환. 원본은 건드리지 않는다."""
    buf = list(sql)
    for cm in scan_comments(sql):
        for k in range(cm.start, min(cm.end, len(buf))):
            if buf[k] != '\n':
                buf[k] = ' '
    return ''.join(buf)


def _mask(sql: str) -> str:
    """주석과 문자열 리터럴을 공백으로 치환 — 코드 구조 분석용."""
    buf = list(_strip_comments_for_scan(sql))
    s = ''.join(buf); i, n = 0, len(s)
    while i < n:
        if s[i] in "'\"":
            q, st = s[i], i; i += 1
            while i < n:
                if s[i] == q:
                    if q == "'" and i + 1 < n and s[i + 1] == "'":
                        i += 2; continue
                    break
                i += 1
            for k in range(st, min(i + 1, n)):
                if buf[k] != '\n':
                    buf[k] = ' '
        i += 1
    return ''.join(buf)


# ── 위반 리포트 ──────────────────────────────────────────────────────────────
@dataclass
class Violation:
    code: str          # PLSQL001 ...
    line: int
    message: str
    auto_fixed: bool = False


@dataclass
class GuardResult:
    sql: str
    violations: list[Violation] = field(default_factory=list)

    @property
    def blocking(self) -> list[Violation]:
        return [v for v in self.violations if not v.auto_fixed]

    def as_report(self) -> str:
        if not self.violations:
            return ''
        rows = [f"  [{v.code}] L{v.line}: {v.message}"
                f"{' → 자동 보정됨' if v.auto_fixed else ' → ★수동 확인 필요'}"
                for v in self.violations]
        return "PL/SQL 전용 점검 결과\n" + "\n".join(rows)


def _lineno(sql: str, pos: int) -> int:
    return sql.count('\n', 0, pos) + 1


# ── PLSQL001: EXCEPTION 절을 가진 블록 안의 COMMIT / ROLLBACK ───────────────
# 문장으로서의 COMMIT/ROLLBACK 만 잡는다. 줄 단위(^...$)로 보면
# `WHEN OTHERS THEN pRETVAL := 256; ROLLBACK;` 처럼 한 줄에 다른 구문과 같이 있는 경우를 놓친다.
_TXN = re.compile(r'(?<![\w.])(COMMIT|ROLLBACK)\s*(?:WORK\s*)?;', re.I)

# 바로 앞에 올 수 있는 것 — 문장 경계임을 보장한다.
# (`SELECT commit FROM t;` 같은 컬럼명 오탐을 막는다)
_STMT_BOUNDARY = re.compile(r'(?:^|[;>]|\b(?:THEN|ELSE|BEGIN|LOOP|DECLARE|DO)\b)\s*$', re.I)

# 인라인 위치에서도 안전하도록 블록 주석으로 치환한다.
# `--` 로 바꾸면 같은 줄 뒤에 남은 구문까지 주석 처리되어 버린다.
_NOTE001 = ('/* [AQMS-PLSQL001] 원본의 {kw} 제거 — PL/pgSQL은 EXCEPTION 절을 가진 블록 안에서 '
            '트랜잭션을 제어할 수 없다(SQLSTATE 2D000). 최종 커밋은 호출자가 수행. */')


def _has_exception_clause(masked: str) -> bool:
    return bool(re.search(r'\bEXCEPTION\b\s+WHEN\b', masked, re.I))


def fix_transaction_control(sql: str) -> tuple[str, list[Violation]]:
    """EXCEPTION 핸들러가 하나라도 있으면 COMMIT/ROLLBACK 문장을 주석으로 대체."""
    masked = _mask(sql)
    if not _has_exception_clause(masked):
        return sql, []
    vios, out, last = [], [], 0
    for m in _TXN.finditer(masked):
        if not _STMT_BOUNDARY.search(masked[:m.start()]):
            continue                      # 문장이 아니라 식별자 등
        kw = m.group(1).upper()
        vios.append(Violation('PLSQL001', _lineno(sql, m.start()),
                              f'EXCEPTION 절이 있는 블록 내 {kw} — 런타임 2D000', True))
        out.append(sql[last:m.start()])
        out.append(_NOTE001.format(kw=kw))
        last = m.end()
    out.append(sql[last:])
    return ''.join(out), vios


# ── PLSQL002: SELECT ... INTO 에 STRICT 누락 ────────────────────────────────
# `INTO    STRICT x` 처럼 공백이 여러 개일 때 \s+ 가 백트래킹하면서
# 부정 선읽기를 빠져나가 재삽입되는 버그가 있었다. 선읽기를 INTO 직후로 고정한다.
_INTO = re.compile(r'(?<![\w.])INTO(?!\s+STRICT\b)\s+', re.I)
_SELECT_HEAD = re.compile(r'\bSELECT\b', re.I)
_COUNT_AGG = re.compile(r'\bSELECT\b[^;]*?\bCOUNT\s*\(', re.I | re.S)


def _enclosing_block_has_handler(masked: str, pos: int) -> bool:
    """pos가 속한 가장 안쪽 BEGIN..END 블록에 EXCEPTION WHEN 이 있는지."""
    tokens = [(m.start(), m.group(0).upper())
              for m in re.finditer(r'\b(BEGIN|END|EXCEPTION)\b', masked, re.I)]
    depth, begin_stack = 0, []
    handler_at_depth: dict[int, bool] = {}
    for p, tok in tokens:
        if tok == 'BEGIN':
            depth += 1; begin_stack.append(p); handler_at_depth[depth] = False
        elif tok == 'EXCEPTION':
            if depth:
                handler_at_depth[depth] = True
        elif tok == 'END':
            if p > pos and begin_stack and begin_stack[-1] < pos:
                return handler_at_depth.get(depth, False)
            if depth:
                depth -= 1
                if begin_stack:
                    begin_stack.pop()
    return False


def fix_select_into_strict(sql: str) -> tuple[str, list[Violation]]:
    """
    EXCEPTION 핸들러가 붙은 블록 안의 `SELECT ... INTO`에 STRICT를 부여한다.
    Oracle: 0건 NO_DATA_FOUND / 2건+ TOO_MANY_ROWS.  PG: STRICT 없으면 둘 다 조용히 통과.
    집계(COUNT/SUM/MIN/MAX/AVG)는 항상 1행이므로 제외.
    """
    masked = _mask(sql)
    edits, vios = [], []
    for m in _INTO.finditer(masked):
        head = None
        for s in _SELECT_HEAD.finditer(masked, 0, m.start()):
            head = s
        if head is None:
            continue                      # INSERT INTO 등
        seg = masked[head.start():m.start()]
        if re.search(r'\b(INSERT|UPDATE|DELETE|MERGE)\b', seg, re.I):
            continue
        if re.search(r'\b(COUNT|SUM|MIN|MAX|AVG)\s*\(', seg, re.I):
            continue                      # 집계는 항상 1행
        if not _enclosing_block_has_handler(masked, m.start()):
            continue
        edits.append(m.end())
        vios.append(Violation('PLSQL002', _lineno(sql, m.start()),
                              'SELECT INTO에 STRICT 누락 — NO_DATA_FOUND/TOO_MANY_ROWS 미발생', True))
    for pos in reversed(edits):
        sql = sql[:pos] + 'STRICT ' + sql[pos:]
    return sql, vios


# ── PLSQL003: 블록주석 중첩 (PG는 중첩 지원, Oracle은 아님) ─────────────────
def fix_nested_block_comment(sql: str) -> tuple[str, list[Violation]]:
    vios, out, last = [], [], 0
    for cm in scan_comments(sql):
        if cm.kind != 'block':
            continue
        body = cm.text[2:-2] if cm.text.endswith('*/') else cm.text[2:]
        if '/*' not in body:
            continue
        # 첫 줄 끝에 '*/' 를 넣어 Oracle 원문 의미대로 닫아 준다.
        nl = sql.find('\n', cm.start)
        if nl < 0 or nl > cm.end:
            continue
        vios.append(Violation('PLSQL003', _lineno(sql, cm.start),
                              '블록주석 안에 /* 재등장 — PG는 중첩 주석이라 이후 전체가 주석 처리됨', True))
        out.append(sql[last:nl])
        out.append('  */ -- [AQMS-PLSQL003] PG 중첩 블록주석 방지용 종료')
        last = nl
    out.append(sql[last:])
    return ''.join(out), vios


# ── PLSQL004: 주석 유실 (검출만, 자동 복원 불가) ────────────────────────────
def check_dropped_comments(original: str, converted: str) -> list[Violation]:
    # 변환 결과의 '주석'끼리만 대조한다. 본문 코드와 비교하면
    # 주석 처리된 이전 WHERE절(`--WHERE CMID = pCMID`)이 살아있는 코드와 매칭되어
    # 유실을 놓친다(위음성).
    conv = ' | '.join(' '.join(c.text.strip('-/* \t').split())
                      for c in scan_comments(converted))
    vios = []
    for cm in scan_comments(original):
        core = cm.text.strip('-/* \t')
        core = ' '.join(core.split())
        if len(core) < 4:
            continue
        if core[:40] not in conv:
            vios.append(Violation('PLSQL004', _lineno(original, cm.start),
                                  f'원본 주석 유실: {core[:50]}', False))
    return vios


# ── 진입점 ───────────────────────────────────────────────────────────────────
def guard_plsql(converted_sql: str, original_sql: str | None = None) -> GuardResult:
    """PL/SQL 변환 결과에만 적용. 호출 전 반드시 is_plsql_source(original)로 게이트할 것."""
    sql = converted_sql
    all_v: list[Violation] = []
    for fn in (fix_nested_block_comment, fix_transaction_control, fix_select_into_strict):
        sql, v = fn(sql)
        all_v += v
    if original_sql:
        all_v += check_dropped_comments(original_sql, sql)
    all_v.sort(key=lambda v: (v.code, v.line))
    return GuardResult(sql, all_v)
