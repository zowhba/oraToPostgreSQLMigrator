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
    </div>

    <!-- 변환 설정 (모델 선택) -->
    <div class="section-card model-picker-section" v-if="queries.length > 0 && results.length === 0 && !loading">
      <div class="model-picker-header">
        <h3 class="section-title">
          <span class="icon">🤖</span> 사용할 AI 모델
          <span class="optional-label">(기본값: 전역 설정 모델 · Admin이 활성화한 모델 중 선택)</span>
        </h3>
      </div>
      <div class="model-picker-body">
        <select v-model="selectedModel" class="form-input model-select" :disabled="availableModels.length === 0">
          <option v-for="m in availableModels" :key="m.id" :value="m.id">
            {{ m.name }}{{ m.id === defaultModel ? ' (기본값)' : '' }}
          </option>
        </select>
        <p class="hint-text">선택한 모델은 이번 변환에만 적용되며 전역 기본값은 변경되지 않습니다.</p>
      </div>
    </div>

    <!-- 변환 설정 (프롬프트 편집) -->
    <div class="section-card prompt-override-section" v-if="queries.length > 0 && results.length === 0 && !loading">
      <div class="section-header" @click="showPromptEditor = !showPromptEditor">
        <h3 class="section-title">
          <span class="icon">⚙️</span> 변환 프롬프트 설정
          <span class="optional-label">(프로젝트 설정을 기반으로 하며, 이번 1회 변환에만 적용됩니다)</span>
        </h3>
        <span class="toggle-icon">{{ showPromptEditor ? '▲' : '▼' }}</span>
      </div>

      <div v-if="showPromptEditor" class="prompt-editor-body">
        <textarea
          v-model="oneTimePrompt"
          class="form-input prompt-textarea"
          placeholder="이 프로젝트의 기본 지침을 기반으로 이번 변환에만 적용할 내용을 수정하세요. 비워두면 프로젝트 설정값이 사용됩니다."
          rows="5"
        ></textarea>
        <p class="hint-text">입력한 내용은 저장되지 않으며 이번 변환 세션에만 적용됩니다.</p>
      </div>
    </div>

    <!-- 변환 버튼 및 상태 -->
    <div class="action-bar" v-if="queries.length > 0">
      <span class="query-count">{{ queries.length }}개 쿼리 발견</span>
      <div class="action-right" v-if="!loading && results.length === 0">
        <button
          class="btn btn-primary"
          @click="handleConvert"
        >
          변환 시작하기
        </button>
      </div>
    </div>

    <!-- 변환 로딩/진행 상태 -->
    <div class="section-card progress-section" v-if="loading">
      <div class="progress-header">
        <div class="status-info">
          <span class="spinner-small"></span>
          <span class="status-msg">{{ statusMessage }}</span>
        </div>
        <div class="eta-info" v-if="estimatedTime > 0">
          남은 예상 시간: <strong>{{ Math.ceil(estimatedTime) }}초</strong>
        </div>
      </div>
      
      <div class="progress-container">
        <div class="progress-bar-bg">
          <div 
            class="progress-bar-fill" 
            :style="{ width: `${progress}%` }"
          ></div>
        </div>
        <span class="progress-percent">{{ progress }}%</span>
      </div>
      
      <p class="progress-hint">대량의 쿼리 변환 시 수 분이 소요될 수 있습니다. 창을 닫지 마세요.</p>
    </div>

    <!-- 결과 테이블 -->
    <div class="section-card" v-if="results.length > 0">
      <div class="section-title-row">
        <h3 class="section-title">변환 결과</h3>
        <span class="model-info-badge" v-if="usedModel">
          사용 모델: <strong>{{ usedModel }}</strong>
        </span>
      </div>
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
import { convertQueriesStream, getHistoryDetail, getSettings, getEnabledModels } from '../api/index.js'
import * as XLSX from 'xlsx'

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
      progress: 0,
      statusMessage: '',
      estimatedTime: 0,
      usedModel: '',
      showPromptEditor: false,
      oneTimePrompt: '',
      globalPrompt: '',
      defaultModel: '',
      selectedModel: '',
      enabledModelIds: [],
      modelCatalog: [
        { id: 'gpt-5.2-chat', name: 'Azure ChatGPT 5.2' },
        { id: 'haiku-4.5', name: 'Claude 4.5 Haiku' },
        { id: 'sonnet-4.5', name: 'Claude 4.5 Sonnet' },
        { id: 'opus-4.6', name: 'Claude 4.6 Opus' }
      ]
    }
  },
  computed: {
    availableModels() {
      return this.modelCatalog.filter(m => this.enabledModelIds.includes(m.id))
    }
  },
  async mounted() {
    await this.fetchGlobalPrompt()
    await this.fetchModelOptions()
    this.checkHistoryParam()
  },
  methods: {
    async checkHistoryParam() {
      const historyId = this.$route.query.historyId
      if (historyId) {
        this.loading = true
        this.statusMessage = '과거 작업 히스토리를 불러오는 중...'
        try {
          const response = await getHistoryDetail(historyId)
          if (response.status === 'success') {
            this.loadFromHistory(response.data)
          }
        } catch (error) {
          console.error('History fetch error:', error)
          alert('히스토리 정보를 불러오지 못했습니다.')
        } finally {
          this.loading = false
          // URL에서 파라미터 제거
          this.$router.replace({ path: '/convert' })
        }
      }
    },

    async fetchGlobalPrompt() {
      try {
        const settings = await getSettings()
        if (settings && settings.global_system_prompt) {
          this.globalPrompt = settings.global_system_prompt
        }
        if (settings && settings.active_model) {
          this.defaultModel = settings.active_model
        }
      } catch (error) {
        console.error('Failed to fetch global prompt:', error)
      }
    },

    async fetchModelOptions() {
      try {
        const res = await getEnabledModels()
        if (res && Array.isArray(res.models)) {
          this.enabledModelIds = res.models
        }
      } catch (error) {
        console.error('Failed to fetch enabled models:', error)
        this.enabledModelIds = ['gpt-5.2-chat', 'haiku-4.5', 'sonnet-4.5', 'opus-4.6']
      }
      // 기본 선택값: 전역 active_model이 활성 목록에 있으면 그걸, 아니면 첫 번째
      if (this.enabledModelIds.includes(this.defaultModel)) {
        this.selectedModel = this.defaultModel
      } else if (this.enabledModelIds.length > 0) {
        this.selectedModel = this.enabledModelIds[0]
      }
    },

    loadFromHistory(data) {
      this.fileName = data.xml_file_name
      this.namespace = data.project_id // namespace 대신 project_id로 저장되어 있으므로 적절히 대응
      this.queries = data.queries.map(q => ({
        query_id: q.query_id,
        tag_name: q.tag_name,
        original_sql_xml: q.original_sql_xml
      }))
      this.results = data.queries
      this.usedModel = data.used_model || ''
      this.selectedQuery = null
    },

    handleFileParsed({ fileName, namespace, queries }) {
      this.fileName = fileName
      this.namespace = namespace
      this.queries = queries
      this.results = []
      this.selectedQuery = null
      // 프로젝트 프롬프트가 있으면 우선 사용, 없으면 전역 공통 프롬프트로 초기화
      this.oneTimePrompt = this.project.system_prompt || this.globalPrompt || ''
    },

    async handleConvert() {
      if (this.queries.length === 0) return

      this.loading = true
      this.progress = 0
      this.statusMessage = '변환 준비 중...'
      this.estimatedTime = this.queries.length * 5 // 초기 예상
      this.results = [] // 시작 시 결과 초기화
      this.usedModel = ''

      try {
        const requestData = {
          project_id: this.project.project_id,
          xml_file_name: this.fileName,
          mapper_namespace: this.namespace,
          file_created_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
          queries: this.queries,
          system_prompt_override: this.oneTimePrompt,
          model_override: this.selectedModel || null
        }

        // 스트리밍 호출
        await convertQueriesStream(requestData, (chunk) => {
          if (chunk.type === 'progress') {
            this.statusMessage = chunk.message
            this.progress = Math.round((chunk.current / chunk.total) * 100)
            this.estimatedTime = chunk.estimated_seconds || 0
          } else if (chunk.type === 'query_result') {
            // 개별 결과가 올 때마다 순차적으로 push (실시간 테이블 업데이트)
            this.results.push(chunk.data)
          } else if (chunk.type === 'complete') {
            this.progress = 100
            this.statusMessage = '변환이 완료되었습니다.'
            this.usedModel = chunk.final_response.used_model || ''
          }
        })

      } catch (error) {
        console.error('Conversion Failed:', error)
        alert('변환 중 오류가 발생했습니다: ' + error.message)
      } finally {
        setTimeout(() => {
           this.loading = false
        }, 800) // 완료 메시지 잠깐 보여주기
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

/* ─── 진행 상태 UI ─── */
.progress-section {
  border-left: 4px solid #667eea;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.status-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.spinner-small {
  width: 18px;
  height: 18px;
  border: 2px solid #e2e8f0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.status-msg {
  font-size: 15px;
  font-weight: 600;
  color: #1a202c;
}

.eta-info {
  font-size: 13px;
  color: #718096;
  background: #f7fafc;
  padding: 4px 12px;
  border-radius: 20px;
  border: 1px solid #edf2f7;
}

.progress-container {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 12px;
}

.progress-bar-bg {
  flex: 1;
  height: 12px;
  background: #edf2f7;
  border-radius: 6px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-radius: 6px;
  transition: width 0.4s ease-out;
  position: relative;
}

.progress-bar-fill::after {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(
    90deg,
    rgba(255,255,255,0) 0%,
    rgba(255,255,255,0.3) 50%,
    rgba(255,255,255,0) 100%
  );
  animation: shine 1.5s infinite;
}

@keyframes shine {
  from { transform: translateX(-100%); }
  to { transform: translateX(100%); }
}

.progress-percent {
  font-size: 14px;
  font-weight: 700;
  color: #4a5568;
  min-width: 40px;
}

.progress-hint {
  font-size: 12px;
  color: #a0aec0;
  margin: 0;
}

.section-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title-row .section-title {
  margin-bottom: 0;
}

.model-info-badge {
  font-size: 12px;
  background: #f1f5f9;
  color: #475569;
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.model-info-badge strong {
  color: #4f46e5;
}

/* ─── 모델 선택 UI ─── */
.model-picker-section {
  padding: 16px 24px !important;
}

.model-picker-header .section-title {
  margin-bottom: 0;
  font-size: 15px;
}

.model-picker-body {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.model-select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  background: #fdfdfd;
  cursor: pointer;
}

.model-select:focus {
  outline: none;
  border-color: #667eea;
  background: #fff;
}

/* ─── 프롬프트 오버라이드 UI ─── */
.prompt-override-section {
  padding: 16px 24px !important;
}

.prompt-override-section .section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
}

.prompt-override-section .section-title {
  margin-bottom: 0;
  font-size: 15px;
}

.optional-label {
  font-size: 12px;
  color: #888;
  font-weight: 400;
  margin-left: 8px;
}

.prompt-editor-body {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.prompt-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.5;
  background: #fdfdfd;
}

.hint-text {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 8px;
}
</style>
