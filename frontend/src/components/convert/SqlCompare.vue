<template>
  <div class="sql-compare">
    <div class="compare-toolbar">
      <label class="sync-toggle">
        <input type="checkbox" v-model="syncScroll" />
        <span>스크롤 연동</span>
      </label>
      <span class="toolbar-hint">
        한쪽을 스크롤하면 대응하는 위치가 반대편에도 함께 보입니다
      </span>
    </div>

    <div class="compare-container">
      <!-- 원본 SQL -->
      <div class="sql-panel">
        <div class="panel-header oracle">
          <span class="panel-title">원본 (Oracle)</span>
          <span class="line-count">{{ originalLines.length }}줄</span>
        </div>
        <div
          class="sql-code"
          ref="origPane"
          @scroll.passive="onScroll('orig')"
        >
          <div
            v-for="(line, index) in originalLines"
            :key="'orig-' + index"
            :class="['code-line', { 'line-removed': align.origChanged[index] }]"
          >
            <span class="line-number">{{ index + 1 }}</span>
            <span class="line-content">{{ line || ' ' }}</span>
          </div>
        </div>
      </div>

      <!-- 변환 SQL -->
      <div class="sql-panel">
        <div class="panel-header postgresql">
          <span class="panel-title">변환 (PostgreSQL)</span>
          <span class="line-count">{{ convertedLines.length }}줄</span>
        </div>
        <div
          class="sql-code"
          ref="convPane"
          @scroll.passive="onScroll('conv')"
        >
          <div
            v-for="(line, index) in convertedLines"
            :key="'conv-' + index"
            :class="['code-line', { 'line-added': align.convChanged[index] }]"
          >
            <span class="line-number">{{ index + 1 }}</span>
            <span class="line-content">{{ line || ' ' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 변경 요약 -->
    <div class="change-summary" v-if="changedCount > 0">
      <span class="summary-badge removed">원본에서 바뀐 줄 {{ removedCount }}</span>
      <span class="summary-badge added">변환에서 추가·수정된 줄 {{ addedCount }}</span>
    </div>
  </div>
</template>

<script>
import { alignLines, syncedScrollTop } from '../../utils/lineAlign.js'

export default {
  name: 'SqlCompare',
  props: {
    originalSql: {
      type: String,
      default: ''
    },
    convertedSql: {
      type: String,
      default: ''
    }
  },
  data() {
    return {
      syncScroll: true
    }
  },
  created() {
    // 반응형일 필요가 없고, 스크롤마다 바뀌므로 data 에 두지 않는다.
    // 두 패널이 서로를 밀어내는 무한 루프를 막는 플래그.
    this.syncing = false
  },
  computed: {
    originalLines() {
      return this.originalSql.split('\n')
    },
    convertedLines() {
      return this.convertedSql.split('\n')
    },
    /**
     * 두 SQL의 줄 대응 관계. 스크롤 연동과 변경 하이라이트가 같이 쓴다.
     * 같은 인덱스끼리 비교하면 줄이 하나만 삽입돼도 그 뒤가 전부 변경으로 표시된다.
     */
    align() {
      return alignLines(this.originalLines, this.convertedLines)
    },
    removedCount() {
      return this.align.origChanged.filter(Boolean).length
    },
    addedCount() {
      return this.align.convChanged.filter(Boolean).length
    },
    changedCount() {
      return this.removedCount + this.addedCount
    }
  },
  watch: {
    syncScroll(on) {
      // 켜는 순간 한 번 맞춰 준다. 끈 상태에서 벌어져 있던 위치를 그대로 두면 어색하다.
      if (on) this.$nextTick(() => this.onScroll('orig'))
    }
  },
  methods: {
    /**
     * 패널의 줄 높이와 첫 줄까지의 여백. 컨테이너 padding 때문에
     * scrollTop 을 그냥 줄 높이로 나누면 한 줄씩 어긋난다.
     */
    paneMetrics(pane) {
      const first = pane.querySelector('.code-line')
      if (!first) return null
      const pr = pane.getBoundingClientRect()
      const fr = first.getBoundingClientRect()
      if (!fr.height) return null
      return { h: fr.height, pad: fr.top - pr.top + pane.scrollTop }
    },

    onScroll(side) {
      if (!this.syncScroll || this.syncing) return

      const from = side === 'orig' ? this.$refs.origPane : this.$refs.convPane
      const to = side === 'orig' ? this.$refs.convPane : this.$refs.origPane
      if (!from || !to) return

      const mFrom = this.paneMetrics(from)
      const mTo = this.paneMetrics(to)
      if (!mFrom || !mTo) return

      this.syncing = true
      to.scrollTop = syncedScrollTop(this.align, side, from.scrollTop, mFrom, mTo)
      to.scrollLeft = from.scrollLeft
      // 위 대입으로 반대편 scroll 이벤트가 발생한다. 그게 되돌아오지 않도록
      // 다음 프레임에 해제한다.
      requestAnimationFrame(() => {
        this.syncing = false
      })
    }
  }
}
</script>

<style scoped>
.sql-compare {
  margin-top: 16px;
}

.compare-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 13px;
}

.sync-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  font-weight: 600;
  color: #334155;
}

.sync-toggle input {
  cursor: pointer;
  margin: 0;
}

.toolbar-hint {
  color: #94a3b8;
  font-size: 12px;
}

.compare-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.sql-panel {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.panel-header {
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-header.oracle {
  background: #fff3e0;
  color: #e65100;
}

.panel-header.postgresql {
  background: #e3f2fd;
  color: #1565c0;
}

.line-count {
  font-size: 12px;
  font-weight: 400;
  opacity: 0.7;
}

.sql-code {
  margin: 0;
  padding: 8px 0;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: #fafafa;
  overflow-x: auto;
  min-height: 150px;
  max-height: 400px;
  overflow-y: auto;
}

.code-line {
  display: flex;
  padding: 2px 12px;
  transition: background 0.15s;
}

.code-line:hover {
  background: #f0f0f0;
}

.line-number {
  min-width: 35px;
  color: #999;
  text-align: right;
  padding-right: 12px;
  user-select: none;
  border-right: 1px solid #e0e0e0;
  margin-right: 12px;
}

.line-content {
  white-space: pre;
  flex: 1;
}

/* 변경된 라인 하이라이트 */
.line-removed {
  background: #ffebee;
}

.line-removed .line-content {
  color: #c62828;
}

.line-removed .line-number {
  background: #ffcdd2;
  color: #b71c1c;
}

.line-added {
  background: #e8f5e9;
}

.line-added .line-content {
  color: #2e7d32;
}

.line-added .line-number {
  background: #c8e6c9;
  color: #1b5e20;
}

/* 변경 요약 */
.change-summary {
  margin-top: 12px;
  text-align: center;
}

.summary-badge {
  display: inline-block;
  padding: 6px 16px;
  margin: 0 4px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
}

.summary-badge.removed {
  background: #ffebee;
  color: #c62828;
}

.summary-badge.added {
  background: #e8f5e9;
  color: #2e7d32;
}

@media (max-width: 768px) {
  .compare-container {
    grid-template-columns: 1fr;
  }
}
</style>
