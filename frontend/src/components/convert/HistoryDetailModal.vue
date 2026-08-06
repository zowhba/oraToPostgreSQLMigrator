<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal-panel" role="dialog" aria-modal="true">
      <!-- 헤더 -->
      <div class="modal-header">
        <div class="header-main">
          <h3 class="modal-title">
            변환 결과
            <span class="readonly-chip" title="이 화면에서는 신규 변환을 실행할 수 없습니다.">읽기 전용</span>
          </h3>
          <p class="modal-sub" v-if="detail">
            {{ detail.project_name }} · {{ detail.xml_file_name }}
            <span class="dim" v-if="detail.created_at"> · {{ formatDate(detail.created_at) }}</span>
          </p>
        </div>
        <button class="btn-close" @click="$emit('close')" aria-label="닫기">✕</button>
      </div>

      <!-- 본문 -->
      <div class="modal-body">
        <div v-if="loading" class="state-box">
          <div class="spinner"></div>
          <p>변환 결과를 불러오는 중...</p>
        </div>

        <div v-else-if="error" class="state-box error">
          <div class="state-icon">⚠️</div>
          <p>{{ error }}</p>
          <button class="btn btn-secondary" @click="fetchDetail">다시 시도</button>
        </div>

        <template v-else-if="detail">
          <!-- 요약 지표 -->
          <div class="summary-grid">
            <div class="summary-item">
              <span class="s-label">쿼리 수</span>
              <span class="s-value">{{ detail.queries.length }}개</span>
            </div>
            <div class="summary-item">
              <span class="s-label">Dry-run 성공</span>
              <span class="s-value">{{ successCount }}/{{ detail.queries.length }}</span>
            </div>
            <div class="summary-item">
              <span class="s-label">난이도 (1/2/3)</span>
              <span class="s-value">
                {{ detail.levels.l1 }} / {{ detail.levels.l2 }} / {{ detail.levels.l3 }}
              </span>
            </div>
            <div class="summary-item">
              <span class="s-label">소요 시간</span>
              <span class="s-value">{{ detail.duration_seconds || 0 }}초</span>
            </div>
            <div class="summary-item">
              <span class="s-label">사용 모델</span>
              <span class="s-value">{{ detail.used_model || '-' }}</span>
            </div>
            <div class="summary-item">
              <span class="s-label">토큰 (In/Out)</span>
              <span class="s-value">
                {{ formatTokens(detail.total_input_tokens) }} / {{ formatTokens(detail.total_output_tokens) }}
              </span>
            </div>
          </div>

          <!-- 쿼리 목록 -->
          <QueryTable :queries="detail.queries" @select="selectedQuery = $event" />

          <!-- 선택된 쿼리 상세 -->
          <div v-if="selectedQuery" class="detail-block">
            <QueryDetail :query="selectedQuery" @close="selectedQuery = null" />
          </div>
        </template>
      </div>

      <!-- 푸터 -->
      <div class="modal-footer">
        <span class="footer-hint">
          이력 조회 화면입니다. 새로운 변환은 '쿼리 변환' 메뉴에서 실행하세요.
        </span>
        <div class="footer-actions">
          <button
            class="btn btn-secondary"
            v-if="detail && detail.queries.length > 0"
            @click="downloadResult"
          >결과 파일 다운로드</button>
          <button class="btn btn-secondary" @click="$emit('close')">닫기</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import QueryTable from './QueryTable.vue'
import QueryDetail from './QueryDetail.vue'
import { getHistoryDetail } from '../../api'
import * as XLSX from 'xlsx'

export default {
  name: 'HistoryDetailModal',
  components: { QueryTable, QueryDetail },
  props: {
    conversionId: {
      type: [Number, String],
      required: true
    }
  },
  emits: ['close'],
  data() {
    return {
      loading: false,
      error: '',
      detail: null,
      selectedQuery: null
    }
  },
  computed: {
    successCount() {
      if (!this.detail) return 0
      return this.detail.queries.filter(
        q => q.dry_run_result && q.dry_run_result.is_success
      ).length
    }
  },
  watch: {
    conversionId: {
      immediate: true,
      handler() {
        this.fetchDetail()
      }
    }
  },
  mounted() {
    document.addEventListener('keydown', this.onKeydown)
  },
  beforeUnmount() {
    document.removeEventListener('keydown', this.onKeydown)
  },
  methods: {
    onKeydown(e) {
      if (e.key !== 'Escape') return
      // 쿼리 상세가 열려 있으면 그것부터 닫는다
      if (this.selectedQuery) this.selectedQuery = null
      else this.$emit('close')
    },

    async fetchDetail() {
      this.loading = true
      this.error = ''
      this.detail = null
      this.selectedQuery = null
      try {
        const res = await getHistoryDetail(this.conversionId)
        if (res.status === 'success') {
          this.detail = res.data
        } else {
          this.error = '변환 결과를 불러오지 못했습니다.'
        }
      } catch (e) {
        const status = e?.response?.status
        if (status === 403) {
          this.error = '이 프로젝트의 이력을 조회할 권한이 없습니다. 관리자에게 문의하세요.'
        } else if (status === 404) {
          this.error = '삭제되었거나 존재하지 않는 이력입니다.'
        } else {
          this.error = e?.response?.data?.detail || '변환 결과를 불러오지 못했습니다.'
        }
      } finally {
        this.loading = false
      }
    },

    formatDate(iso) {
      const d = new Date(iso)
      if (Number.isNaN(d.getTime())) return ''
      return new Intl.DateTimeFormat('ko-KR', {
        timeZone: 'Asia/Seoul',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hour12: false
      }).format(d)
    },

    formatTokens(count) {
      if (!count) return '0'
      if (count >= 1000000) return (count / 1000000).toFixed(1) + 'M'
      if (count >= 1000) return (count / 1000).toFixed(1) + 'K'
      return String(count)
    },

    /** 원본 파일 형식(.sql / .xlsx / .xml)에 맞춰 변환 결과를 내려받습니다. */
    downloadResult() {
      const fileName = this.detail.xml_file_name || 'converted'
      const lower = fileName.toLowerCase()

      if (lower.endsWith('.xlsx') || lower.endsWith('.xls')) {
        const data = this.detail.queries.map(q => [this.stripTags(q.converted_sql)])
        const ws = XLSX.utils.aoa_to_sheet(data)
        const wb = XLSX.utils.book_new()
        XLSX.utils.book_append_sheet(wb, ws, 'Converted Queries')
        const ext = lower.endsWith('.xlsx') ? '.xlsx' : '.xls'
        XLSX.writeFile(wb, fileName.replace(new RegExp(ext + '$', 'i'), '_postgresql' + ext))
        return
      }

      let content
      let outName
      if (lower.endsWith('.sql')) {
        const header = [
          '-- ============================================================',
          `-- AQMS 변환 결과 (원본: ${fileName})`,
          `-- 변환 모델: ${this.detail.used_model || '-'}`,
          '-- ============================================================',
          ''
        ].join('\n')
        content = header + '\n' + this.detail.queries
          .map(q => `-- ── ${q.query_id} (${q.tag_name}) ──\n${q.converted_sql}\n`)
          .join('\n')
        outName = fileName.replace(/\.sql$/i, '') + '_postgresql.sql'
      } else {
        content = '<?xml version="1.0" encoding="UTF-8"?>\n'
          + `<mapper namespace="${this.detail.project_id}">\n\n`
          + this.detail.queries
            .map(q => `  <!-- ${q.query_id} (난이도: ${q.difficulty_level}) -->\n  ${q.converted_sql}\n`)
            .join('\n')
          + '\n</mapper>'
        outName = fileName.replace(/\.xml$/i, '') + '_postgresql.xml'
      }

      const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = outName
      a.click()
      URL.revokeObjectURL(url)
    },

    stripTags(xml) {
      if (!xml) return ''
      return xml.replace(/<[^>]+>/g, '').trim()
    }
  }
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}

.modal-panel {
  background: #fff;
  border-radius: 14px;
  width: 100%;
  max-width: 1120px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px 16px;
  border-bottom: 1px solid #eef2f7;
}

.modal-title {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.readonly-chip {
  font-size: 11px;
  font-weight: 700;
  background: #e0e7ff;
  color: #4338ca;
  padding: 2px 8px;
  border-radius: 999px;
}

.modal-sub {
  margin: 0;
  font-size: 13px;
  color: #64748b;
}

.dim { color: #94a3b8; }

.btn-close {
  background: #f1f5f9;
  border: none;
  color: #475569;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
}

.btn-close:hover { background: #e2e8f0; }

.modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}

.summary-item {
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.s-label { font-size: 11px; color: #94a3b8; font-weight: 600; }
.s-value { font-size: 14px; color: #1e293b; font-weight: 700; }

.detail-block {
  margin-top: 18px;
  border-top: 1px solid #eef2f7;
  padding-top: 18px;
}

.state-box {
  text-align: center;
  padding: 70px 20px;
  color: #94a3b8;
}

.state-box.error { color: #b91c1c; }
.state-icon { font-size: 40px; margin-bottom: 12px; }

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #f1f5f9;
  border-top-color: #6366f1;
  border-radius: 50%;
  margin: 0 auto 14px;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 24px;
  border-top: 1px solid #eef2f7;
  background: #fafbfd;
}

.footer-hint { font-size: 12px; color: #94a3b8; }
.footer-actions { display: flex; gap: 8px; }

.btn {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}

.btn-secondary {
  background: #f1f5f9;
  color: #334155;
  border: 1px solid #e2e8f0;
}

.btn-secondary:hover { background: #e2e8f0; }
</style>
