/**
 * SQL 비교 줄 정렬 / 스크롤 연동 매핑 테스트
 * 실행: npm run test:linealign
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { alignLines, mapIndex } from '../src/utils/lineAlign.js'

const L = (s) => s.split('\n')

test('완전히 같으면 모든 줄이 1:1로 짝지어진다', () => {
  const a = L('a\nb\nc')
  const r = alignLines(a, a)
  assert.deepEqual(r.pairs, [[0, 0], [1, 1], [2, 2]])
  assert.deepEqual(r.origChanged, [false, false, false])
})

test('줄 하나가 삽입돼도 뒤쪽이 전부 변경으로 뒤틀리지 않는다', () => {
  // 인덱스 단순 비교의 고질적 문제 — 이게 이 모듈의 존재 이유다
  const orig = L('a\nb\nc\nd')
  const conv = L('a\nNEW\nb\nc\nd')
  const r = alignLines(orig, conv)
  assert.deepEqual(r.origChanged, [false, false, false, false]) // 원본은 전부 살아있다
  assert.deepEqual(r.convChanged, [false, true, false, false, false]) // NEW 만 추가
})

test('삭제된 줄만 변경으로 표시된다', () => {
  const r = alignLines(L('a\nGONE\nb'), L('a\nb'))
  assert.deepEqual(r.origChanged, [false, true, false])
  assert.deepEqual(r.convChanged, [false, false])
})

test('공백 차이는 같은 줄로 본다 (기존 trim 비교 유지)', () => {
  const r = alignLines(L('  a  \nb'), L('a\n   b'))
  assert.deepEqual(r.origChanged, [false, false])
})

test('삽입된 줄을 건너뛰고 대응 줄을 찾는다', () => {
  const align = alignLines(L('a\nb\nc\nd'), L('a\nX\nY\nb\nc\nd'))
  assert.equal(mapIndex(align, 0, 'orig'), 0)
  assert.equal(mapIndex(align, 1, 'orig'), 3) // 원본 b → 변환 b
  assert.equal(mapIndex(align, 3, 'orig'), 5)
})

test('역방향 매핑도 대칭이다', () => {
  const align = alignLines(L('a\nb\nc\nd'), L('a\nX\nY\nb\nc\nd'))
  assert.equal(mapIndex(align, 3, 'conv'), 1) // 변환 b → 원본 b
  assert.equal(mapIndex(align, 5, 'conv'), 3)
})

test('짝 없는 줄은 앞뒤 사이를 비례 보간한다 (스크롤이 튀지 않게)', () => {
  const align = alignLines(L('a\nb\nc\nd'), L('a\nX\nY\nb\nc\nd'))
  const mid = mapIndex(align, 0.5, 'orig')
  assert.ok(mid > 0 && mid < 3, `0과 3 사이여야 함: ${mid}`)
})

test('매핑은 단조 증가한다 (스크롤이 거꾸로 가면 안 됨)', () => {
  const align = alignLines(
    L(Array.from({ length: 40 }, (_, i) => `line ${i}`).join('\n')),
    L(Array.from({ length: 60 }, (_, i) => (i % 3 ? `line ${i - Math.floor(i / 3)}` : `EXTRA ${i}`)).join('\n'))
  )
  let prev = -1
  for (let i = 0; i <= 40; i += 0.5) {
    const v = mapIndex(align, i, 'orig')
    assert.ok(v >= prev - 1e-9, `역행: i=${i} ${prev} → ${v}`)
    prev = v
  }
})

test('빈 입력에서도 죽지 않는다', () => {
  const r = alignLines([], [])
  assert.deepEqual(r.pairs, [])
  assert.equal(mapIndex(r, 0, 'orig'), 0)
  const r2 = alignLines(L('a\nb'), [])
  assert.equal(mapIndex(r2, 1, 'orig'), 0)
})

test('한쪽이 통째로 다르면 짝이 없다', () => {
  const r = alignLines(L('a\nb'), L('x\ny'))
  assert.deepEqual(r.origChanged, [true, true])
  assert.deepEqual(r.convChanged, [true, true])
})

test('끝부분 공통 구간(접미)도 정렬된다', () => {
  const r = alignLines(L('HEAD1\nsame1\nsame2'), L('HEAD_A\nHEAD_B\nsame1\nsame2'))
  assert.equal(r.origChanged[1], false)
  assert.equal(r.origChanged[2], false)
  assert.equal(r.convChanged[0], true)
})

test('실제 PL/SQL 변환 형태 — 원본 줄 대부분이 보존된다', () => {
  const orig = L([
    'CREATE OR REPLACE PROCEDURE p (', '  pCMID VARCHAR2', ')', 'AS', 'spTemp CHAR(1);',
    'BEGIN', "  spTemp := '';", '  SELECT c INTO v FROM t;', '  COMMIT;',
    'EXCEPTION', '  WHEN OTHERS THEN NULL;', 'END p;'
  ].join('\n'))
  const conv = L([
    'CREATE OR REPLACE PROCEDURE p (', '  pCMID VARCHAR', ')', 'LANGUAGE plpgsql', 'AS $$',
    'DECLARE', 'spTemp CHAR(1);', 'BEGIN', '  spTemp := NULL;',
    '  SELECT c INTO STRICT v FROM t;', '  /* [AQMS-PLSQL001] COMMIT 제거 */',
    'EXCEPTION', '  WHEN OTHERS THEN NULL;', 'END;', '$$;'
  ].join('\n'))
  const r = alignLines(orig, conv)
  // 실제로 바뀐 줄만 변경으로 잡혀야 한다
  const changed = r.origChanged.map((c, i) => (c ? i : -1)).filter((i) => i >= 0)
  assert.deepEqual(changed, [
    1,  // VARCHAR2 -> VARCHAR
    3,  // AS -> AS $$
    6,  // := '' -> := NULL
    7,  // INTO -> INTO STRICT
    8,  // COMMIT 제거
    11  // END p; -> END;
  ])
  // 구조 키워드가 서로 짝지어져야 스크롤 위치가 맞는다
  assert.equal(r.origChanged[5], false) // BEGIN
  assert.equal(r.origChanged[9], false) // EXCEPTION
  assert.equal(mapIndex(r, 5, 'orig'), 7)  // 원본 BEGIN(5줄) -> 변환 BEGIN(7줄)
  assert.equal(mapIndex(r, 9, 'orig'), 11) // 원본 EXCEPTION -> 변환 EXCEPTION
})

// ── 스크롤 위치 변환 ──────────────────────────────────────────────
import { syncedScrollTop } from '../src/utils/lineAlign.js'

const M = { h: 24, pad: 8 } // 줄 높이 24px, 위 padding 8px

test('내용이 같으면 스크롤 위치가 그대로 유지된다', () => {
  const a = L('a\nb\nc\nd\ne')
  const align = alignLines(a, a)
  for (const top of [0, 8, 32, 56, 104]) {
    assert.equal(syncedScrollTop(align, 'orig', top, M, M), top)
  }
})

test('padding 을 빼먹으면 한 줄 어긋난다 — pad 가 반영되는지', () => {
  const a = L('a\nb\nc')
  const align = alignLines(a, a)
  // 첫 줄이 화면 맨 위 = scrollTop 8 (pad). 반대편도 8이어야 한다.
  assert.equal(syncedScrollTop(align, 'orig', 8, M, M), 8)
  // pad 를 무시했다면 여기서 32가 아니라 다른 값이 나온다
  assert.equal(syncedScrollTop(align, 'orig', 8 + 24, M, M), 8 + 24)
})

test('줄이 삽입된 만큼 반대편이 더 내려간다', () => {
  const align = alignLines(L('a\nb\nc\nd'), L('a\nX\nY\nb\nc\nd'))
  // 원본 b(1줄)가 맨 위 → 변환 b(3줄)가 맨 위
  assert.equal(syncedScrollTop(align, 'orig', 8 + 24 * 1, M, M), 8 + 24 * 3)
})

test('줄 높이가 서로 달라도 맞는 줄을 띄운다', () => {
  const a = L('a\nb\nc\nd')
  const align = alignLines(a, a)
  const big = { h: 30, pad: 12 }
  assert.equal(syncedScrollTop(align, 'orig', 8 + 24 * 2, M, big), 12 + 30 * 2)
})

test('맨 위에서는 0 아래로 내려가지 않는다', () => {
  const a = L('a\nb')
  const align = alignLines(a, a)
  assert.ok(syncedScrollTop(align, 'orig', 0, M, M) >= 0)
  assert.ok(syncedScrollTop(align, 'orig', -50, M, M) >= 0)
})

test('역방향도 같은 줄로 되돌아온다 (왕복 안정성)', () => {
  const align = alignLines(L('a\nb\nc\nd'), L('a\nX\nY\nb\nc\nd'))
  const origTop = 8 + 24 * 2 // 원본 c
  const convTop = syncedScrollTop(align, 'orig', origTop, M, M)
  const back = syncedScrollTop(align, 'conv', convTop, M, M)
  assert.equal(back, origTop)
})
