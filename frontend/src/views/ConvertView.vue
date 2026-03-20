<template>
  <div class="convert-view">
    <h2 class="page-title">쿼리 변환</h2>
    <p class="page-desc">MyBatis XML 또는 엑셀 파일을 업로드하여 Oracle 쿼리를 PostgreSQL로 변환합니다.</p>

    <!-- 프로젝트 미설정 경고 -->
    <div class="alert alert-warning" v-if="!project.project_id">
      프로젝트 설정이 필요합니다.
      <router-link to="/setting">프로젝트 설정으로 이동</router-link>
    </div>

    <!-- 파일 업로드 -->
    <div class="section-card">
      <FileUpload
        @file-parsed="handleFileParsed"
        :disabled="!project.project_id"
      />

      <!-- 최근 작업 파일 (옵션 3) -->
      <div class="recent-files" v-if="recentHistory.length > 0 && !fileName">
        <h4 class="recent-title">최근 작업 파일</h4>
        <div class="recent-list">
          <div
            v-for="item in recentHistory"
            :key="item.id"
            class="recent-item"
            @click="loadFromHistory(item)"
          >
            <span class="recent-icon">&#128196;</span>
            <div class="recent-info">
              <span class="recent-name">{{ item.fileName }}</span>
              <span class="recent-meta">
                {{ formatDate(item.uploadedAt) }} | {{ item.queryCount }}개 쿼리
              </span>
            </div>
            <span class="recent-arrow">&#8594;</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 변환 버튼 -->
    <div class="action-bar" v-if="queries.length > 0">
      <span class="query-count">{{ queries.length }}개 쿼리 발견</span>
      <button
        class="btn btn-primary"
        @click="handleConvert"
        :disabled="loading"
      >
        {{ loading ? '변환 중...' : '변환하기' }}
      </button>
    </div>

    <!-- 결과 테이블 -->
    <div class="section-card" v-if="results.length > 0">
      <h3 class="section-title">변환 결과</h3>
      <QueryTable
        :queries="results"
        @select="handleSelectQuery"
      />
    </div>

    <!-- 상세 보기 -->
    <div class="section-card" v-if="selectedQuery">
      <QueryDetail
        :query="selectedQuery"
        @close="selectedQuery = null"
      />
    </div>

    <!-- 다운로드 버튼 -->
    <div class="action-bar" v-if="results.length > 0">
      <button class="btn btn-secondary" @click="downloadResult">
        결과 파일 다운로드
      </button>
    </div>
  </div>
</template>

<script>
import FileUpload from '../components/convert/FileUpload.vue'
import QueryTable from '../components/convert/QueryTable.vue'
import QueryDetail from '../components/convert/QueryDetail.vue'
import { convertQueries } from '../api/index.js'
import * as XLSX from 'xlsx'
import {
  getRecentHistory,
  getHistoryById,
  saveHistory,
  formatDate
} from '../utils/historyStorage.js'

export default {
  name: 'ConvertView',
  components: {
    FileUpload,
    QueryTable,
    QueryDetail
  },
  props: {
    project: {
      type: Object,
      required: true
    }
  },
  data() {
    return {
      fileName: '',
      namespace: '',
      queries: [],
      results: [],
      selectedQuery: null,
      loading: false,
      recentHistory: []
    }
  },
  mounted() {
    this.loadRecentHistory()
    this.checkHistoryParam()
  },
  methods: {
    loadRecentHistory() {
      this.recentHistory = getRecentHistory(3)
    },

    checkHistoryParam() {
      const historyId = this.$route.query.historyId
      if (historyId) {
        const history = getHistoryById(historyId)
        if (history) {
          this.loadFromHistory(history)
        }
        // URL에서 파라미터 제거
        this.$router.replace({ path: '/convert' })
      }
    },

    formatDate(isoString) {
      return formatDate(isoString)
    },

    loadFromHistory(item) {
      this.fileName = item.fileName
      this.namespace = item.namespace
      this.queries = item.queries || []
      this.results = item.results || []
      this.selectedQuery = null
    },

    handleFileParsed({ fileName, namespace, queries }) {
      this.fileName = fileName
      this.namespace = namespace
      this.queries = queries
      this.results = []
      this.selectedQuery = null
    },

    async handleConvert() {
      if (this.queries.length === 0) return

      this.loading = true

      try {
        const requestData = {
          project_id: this.project.project_id,
          xml_file_name: this.fileName,
          mapper_namespace: this.namespace,
          file_created_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
          queries: this.queries
        }

        const response = await convertQueries(requestData)
        this.results = response.queries || []

        // 히스토리에 저장
        saveHistory({
          fileName: this.fileName,
          namespace: this.namespace,
          queries: this.queries,
          results: this.results
        })

        // 최근 히스토리 새로고침
        this.loadRecentHistory()

      } catch (error) {
        alert('변환 중 오류가 발생했습니다: ' + error.message)
      } finally {
        this.loading = false
      }
    },

    handleSelectQuery(query) {
      this.selectedQuery = query
    },

    downloadResult() {
      const isExcel = this.fileName.endsWith('.xlsx') || this.fileName.endsWith('.xls')

      if (isExcel) {
        this.downloadExcel()
      } else {
        this.downloadXml()
      }
    },

    downloadXml() {
      let xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
      xml += `<mapper namespace="${this.namespace}">\n\n`

      this.results.forEach(query => {
        xml += `  <!-- ${query.query_id} (난이도: ${query.difficulty_level}) -->\n`
        xml += `  ${query.converted_sql}\n\n`
      })

      xml += '</mapper>'

      const blob = new Blob([xml], { type: 'application/xml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = this.fileName.replace('.xml', '_postgresql.xml')
      a.click()
      URL.revokeObjectURL(url)
    },

    downloadExcel() {
      // 엑셀은 XML 태그 없이 순수 SQL만 한 줄에 하나씩 추출
      const data = this.results.map(query => {
        // 백엔드에서 온 converted_sql에서 태그 제거 (필요시)
        // 여기서는 사용자가 '입력파일과 동일하게' 요청했으므로 순수 SQL 추출 로직 적용
        const pureSql = this.stripTags(query.converted_sql)
        return [pureSql]
      })

      const worksheet = XLSX.utils.aoa_to_sheet(data)
      const workbook = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Converted Queries')

      // 파일 다운로드 실행
      const extension = this.fileName.endsWith('.xlsx') ? '.xlsx' : '.xls'
      const downloadName = this.fileName.replace(extension, '_postgresql' + extension)
      XLSX.writeFile(workbook, downloadName)
    },

    /**
     * XML 태그를 제거하고 순수 내용만 추출 (엑셀용)
     */
    stripTags(xml) {
      if (!xml) return ''
      // <select ...> 와 </select> 태그 및 기타 MyBatis 태그 제거
      // 가장 단순하게는 정규식으로 <...> 를 제거
      return xml.replace(/<[^>]+>/g, '').trim()
    }
  }
}
</script>

<style scoped>
.convert-view {
  max-width: 1200px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.page-desc {
  color: #666;
  margin-bottom: 24px;
}

.alert {
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.alert-warning {
  background: #fff3cd;
  color: #856404;
  border: 1px solid #ffc107;
}

.alert a {
  color: #533f03;
  font-weight: 600;
}

.section-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin-bottom: 20px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}

/* 최근 작업 파일 */
.recent-files {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #eee;
}

.recent-title {
  font-size: 14px;
  font-weight: 600;
  color: #666;
  margin-bottom: 12px;
}

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recent-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #f8f9fa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.recent-item:hover {
  background: #e8edff;
  transform: translateX(4px);
}

.recent-icon {
  font-size: 20px;
}

.recent-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.recent-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.recent-meta {
  font-size: 12px;
  color: #888;
}

.recent-arrow {
  color: #667eea;
  font-size: 16px;
}

.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.query-count {
  font-size: 14px;
  color: #666;
}

.btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.btn-secondary {
  background: #f0f0f0;
  color: #333;
}

.btn-secondary:hover {
  background: #e0e0e0;
}
</style>
