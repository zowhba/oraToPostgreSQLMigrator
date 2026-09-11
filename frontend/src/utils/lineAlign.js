/**
 * 원본 SQL과 변환 SQL의 줄을 대응시킨다.
 *
 * 쓰임 두 가지:
 *   1. 스크롤 연동 — 왼쪽에서 보고 있는 줄에 대응하는 오른쪽 줄을 찾는다.
 *   2. 변경 하이라이트 — 짝을 찾은 줄은 '같음', 못 찾은 줄은 '변경'.
 *
 * 같은 인덱스끼리 비교하면(기존 방식) 줄이 하나만 삽입돼도 그 뒤가 전부
 * 변경으로 표시된다. PL/SQL 변환은 주석·DECLARE 등이 늘어나 줄 수가 달라지므로
 * LCS(최장 공통 부분수열)로 실제 대응 관계를 구한다.
 */

// LCS는 O(n*m). 아주 큰 파일에서 브라우저가 멈추지 않도록 상한을 둔다.
// 넘으면 중간 구간은 짝 없이 남고 mapIndex 가 비율로 보간한다(기존 수준의 동작).
const MAX_CELLS = 4000000

const norm = (line) => line.trim()

function lcsPairs(a, b, offA, offB, an, bn, out) {
  const w = bn + 1
  const dp = new Uint32Array((an + 1) * w)
  for (let i = an - 1; i >= 0; i--) {
    for (let j = bn - 1; j >= 0; j--) {
      dp[i * w + j] =
        a[offA + i] === b[offB + j]
          ? dp[(i + 1) * w + (j + 1)] + 1
          : Math.max(dp[(i + 1) * w + j], dp[i * w + (j + 1)])
    }
  }
  let i = 0
  let j = 0
  while (i < an && j < bn) {
    if (a[offA + i] === b[offB + j]) {
      out.push([offA + i, offB + j])
      i++
      j++
    } else if (dp[(i + 1) * w + j] >= dp[i * w + (j + 1)]) {
      i++
    } else {
      j++
    }
  }
}

/**
 * @returns {{pairs: number[][], n: number, m: number,
 *            origChanged: boolean[], convChanged: boolean[], exact: boolean}}
 *   pairs       대응하는 [원본 인덱스, 변환 인덱스] 쌍 (양쪽 모두 오름차순)
 *   origChanged 원본 줄별 '짝 없음' 여부
 *   exact       LCS 를 끝까지 돌렸는지 (false면 상한에 걸려 일부만 정렬됨)
 */
export function alignLines(origLines, convLines) {
  const n = origLines.length
  const m = convLines.length
  const a = origLines.map(norm)
  const b = convLines.map(norm)

  // 공통 접두/접미를 먼저 떼어내면 LCS 대상이 크게 줄어든다.
  let head = 0
  while (head < n && head < m && a[head] === b[head]) head++
  let tail = 0
  while (tail < n - head && tail < m - head && a[n - 1 - tail] === b[m - 1 - tail]) tail++

  const pairs = []
  for (let i = 0; i < head; i++) pairs.push([i, i])

  const an = n - head - tail
  const bn = m - head - tail
  let exact = true
  if (an > 0 && bn > 0) {
    if (an * bn <= MAX_CELLS) {
      lcsPairs(a, b, head, head, an, bn, pairs)
    } else {
      exact = false
    }
  }

  for (let i = 0; i < tail; i++) pairs.push([n - tail + i, m - tail + i])

  const origChanged = new Array(n).fill(true)
  const convChanged = new Array(m).fill(true)
  for (const [oi, ci] of pairs) {
    origChanged[oi] = false
    convChanged[ci] = false
  }

  return { pairs, n, m, origChanged, convChanged, exact }
}

/**
 * 한쪽 줄 인덱스를 반대쪽 줄 인덱스로 변환한다.
 * 짝이 없는 줄(추가/삭제된 줄)은 앞뒤 짝 사이를 비례 보간해 부드럽게 이어준다.
 *
 * @param side 'orig' | 'conv'  — idx 가 어느 쪽 인덱스인지
 * @returns 실수 인덱스 (스크롤 위치 계산에 그대로 쓴다)
 */
export function mapIndex(align, idx, side = 'orig') {
  const { pairs, n, m } = align
  const fi = side === 'orig' ? 0 : 1
  const ti = 1 - fi
  const total = side === 'orig' ? n : m
  const otherTotal = side === 'orig' ? m : n

  if (!pairs.length) return total > 0 ? (idx / total) * otherTotal : 0

  // idx 이하인 마지막 짝을 찾는다
  let lo = 0
  let hi = pairs.length - 1
  let k = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (pairs[mid][fi] <= idx) {
      k = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  if (k >= 0 && pairs[k][fi] === idx) return pairs[k][ti]

  const loFrom = k >= 0 ? pairs[k][fi] : 0
  const loTo = k >= 0 ? pairs[k][ti] : 0
  const hiFrom = k + 1 < pairs.length ? pairs[k + 1][fi] : total
  const hiTo = k + 1 < pairs.length ? pairs[k + 1][ti] : otherTotal

  const span = hiFrom - loFrom
  const ratio = span > 0 ? (idx - loFrom) / span : 0
  return loTo + ratio * (hiTo - loTo)
}

/**
 * 한쪽 패널의 스크롤 위치를 반대편 패널의 스크롤 위치로 변환한다.
 *
 * 컨테이너 위쪽 padding 때문에 scrollTop 을 줄 높이로 그냥 나누면 한 줄씩 어긋난다.
 * metrics 는 {h: 한 줄 높이, pad: 컨테이너 위쪽부터 첫 줄까지의 거리}.
 *
 * @param side 'orig' | 'conv' — fromScrollTop 이 어느 쪽 패널의 값인지
 */
export function syncedScrollTop(align, side, fromScrollTop, fromMetrics, toMetrics) {
  // 첫 줄에 닿기 전(위쪽 padding 구간)은 줄 인덱스로 환산할 게 없다.
  // 여기서 인덱스를 0으로 잘라 버리면 맨 위에서 반대편이 pad 만큼 내려가 어긋난다.
  if (fromScrollTop <= fromMetrics.pad) {
    const ratio = fromMetrics.pad > 0 ? fromScrollTop / fromMetrics.pad : 0
    return Math.max(0, ratio * toMetrics.pad)
  }
  const index = (fromScrollTop - fromMetrics.pad) / fromMetrics.h
  const mapped = mapIndex(align, index, side)
  return Math.max(0, mapped * toMetrics.h + toMetrics.pad)
}
