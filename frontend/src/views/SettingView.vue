<template>
  <div class="setting-view">
    <!-- 전역 로딩 오버레이 (저장/테스트/상세조회 중) -->
    <LoadingOverlay
      :visible="loadingOverlay"
      :message="loadingMessage"
      :sub-message="loadingSubMessage"
    />

    <h2 class="page-title">프로젝트 설정</h2>
    <p class="page-desc">프로젝트 정보와 대상 PostgreSQL 접속 정보를 관리합니다.</p>

    <div class="setting-layout">
      <!-- 프로젝트 목록 -->
      <div class="project-list-section">
        <div class="section-header">
          <h3 class="section-title">프로젝트 목록</h3>
          <button class="btn btn-sm btn-primary" @click="showNewForm" :disabled="listLoading">
            + 새 프로젝트
          </button>
        </div>

        <!-- 목록 로딩 스켈레톤 -->
        <div class="skeleton-list" v-if="listLoading">
          <div class="skeleton-item" v-for="n in 3" :key="n">
            <div class="skeleton-line long"></div>
            <div class="skeleton-line short"></div>
          </div>
        </div>

        <div class="project-list" v-else-if="projects.length > 0">
          <div
            v-for="proj in projects"
            :key="proj.project_id"
            :class="[
              'project-item',
              { active: selectedProjectId === proj.project_id },
              { current: project.project_id === proj.project_id }
            ]"
            @click="viewProject(proj.project_id)"
          >
            <div class="project-info">
              <span class="project-name">
                {{ proj.project_name }}
                <span v-if="project.project_id === proj.project_id" class="current-badge">사용중</span>
              </span>
              <span class="project-id">{{ proj.project_id }}</span>
              <span class="project-db">{{ proj.db_config_summary }}</span>
            </div>
            <button
              class="btn-delete"
              @click.stop="handleDelete(proj.project_id)"
              title="삭제"
            >
              &#10005;
            </button>
          </div>
        </div>

        <div class="empty-list" v-else>
          <p>등록된 프로젝트가 없습니다.</p>
          <button class="btn btn-primary" @click="showNewForm">
            첫 프로젝트 등록하기
          </button>
        </div>
      </div>

      <!-- 프로젝트 등록/상세 폼 -->
      <div class="project-form-section">
        <div class="form-card" v-if="showForm">
          <div class="form-header">
            <h3 class="form-title">
              {{ isNewProject ? '새 프로젝트 등록' : '프로젝트 상세' }}
            </h3>
            <!-- 현재 선택된 프로젝트 표시 -->
            <span v-if="!isNewProject && project.project_id === form.project_id" class="selected-badge">
              현재 사용중
            </span>
          </div>

          <form @submit.prevent="handleSubmit" class="project-form">
            <!-- 프로젝트 정보 -->
            <div class="form-section">
              <h4 class="section-label">프로젝트 정보</h4>

              <div class="form-group">
                <label class="form-label">프로젝트 ID</label>
                <input
                  type="text"
                  v-model="form.project_id"
                  class="form-input"
                  placeholder="예: PRJ_SKB_001"
                  :disabled="!isNewProject"
                  required
                />
              </div>

              <div class="form-group">
                <label class="form-label">프로젝트 이름</label>
                <input
                  type="text"
                  v-model="form.project_name"
                  class="form-input"
                  placeholder="예: SKB 차세대 마이그레이션"
                  required
                />
              </div>
            </div>

            <!-- DB 접속 정보 -->
            <div class="form-section">
              <h4 class="section-label">PostgreSQL 접속 정보</h4>

              <div class="form-row">
                <div class="form-group flex-1">
                  <label class="form-label">Host</label>
                  <input
                    type="text"
                    v-model="form.db_config.host"
                    class="form-input"
                    placeholder="예: 10.1.2.3"
                    required
                  />
                </div>

                <div class="form-group" style="width: 120px;">
                  <label class="form-label">Port</label>
                  <input
                    type="number"
                    v-model="form.db_config.port"
                    class="form-input"
                    placeholder="5432"
                    required
                  />
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">Database 이름</label>
                <input
                  type="text"
                  v-model="form.db_config.db_name"
                  class="form-input"
                  placeholder="예: target_pg_db"
                  required
                />
              </div>

              <div class="form-group">
                <label class="form-label">스키마 <span class="optional-label">(optional)</span></label>
                <input
                  type="text"
                  v-model="form.db_config.db_schema"
                  class="form-input"
                  placeholder="비워두면 public 사용, 예: edmp"
                />
                <span class="form-hint">테이블이 public 외 특정 스키마에 있을 때 입력하세요</span>
              </div>

              <div class="form-row">
                <div class="form-group flex-1">
                  <label class="form-label">사용자</label>
                  <input
                    type="text"
                    v-model="form.db_config.user"
                    class="form-input"
                    placeholder="예: migrator"
                    required
                  />
                </div>

                <div class="form-group flex-1">
                  <label class="form-label">비밀번호</label>
                  <input
                    type="password"
                    v-model="form.db_config.pw"
                    class="form-input"
                    :placeholder="isNewProject ? '비밀번호 입력' : '기존 비밀번호 유지(********)'"
                  />
                </div>
              </div>
            </div>

            <!-- 메시지 -->
            <div v-if="message.text" :class="['message', message.type]">
              {{ message.text }}
            </div>

            <!-- 버튼 -->
            <div class="form-actions">
              <button
                type="button"
                class="btn btn-secondary"
                @click="handleTestConnection"
                :disabled="!form.db_config.host || testingConnection || loading"
              >
                <span v-if="testingConnection" class="btn-spinner"></span>
                {{ testingConnection ? '테스트 중...' : 'DB 연결 테스트' }}
              </button>

              <div class="action-right">
                <button
                  type="button"
                  class="btn btn-ghost"
                  @click="cancelForm"
                  :disabled="loading || testingConnection"
                >
                  닫기
                </button>
                <button
                  type="submit"
                  class="btn btn-primary"
                  :disabled="loading || testingConnection"
                >
                  <span v-if="loading" class="btn-spinner"></span>
                  {{ loading ? '저장 중...' : (isNewProject ? '등록' : '저장') }}
                </button>
              </div>
            </div>

            <!-- 프로젝트 선택/해제 버튼 (새 프로젝트가 아닌 경우에만 표시) -->
            <div class="select-actions" v-if="!isNewProject">
              <button
                v-if="project.project_id !== form.project_id"
                type="button"
                class="btn btn-select"
                @click="handleSelectProject"
              >
                이 프로젝트 사용하기
              </button>
              <button
                v-else
                type="button"
                class="btn btn-deselect"
                @click="handleDeselectProject"
              >
                프로젝트 선택 해제
              </button>
            </div>
          </form>
        </div>

        <!-- 선택 안내 -->
        <div class="select-guide" v-else>
          <div class="guide-icon">&#128203;</div>
          <p>프로젝트를 선택하거나 새로 등록하세요.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import LoadingOverlay from '../components/layout/LoadingOverlay.vue'
import {
  getProjects,
  getProject,
  saveProject,
  deleteProject,
  testConnection
} from '../api/index.js'

export default {
  name: 'SettingView',
  components: { LoadingOverlay },
  props: {
    project: {
      type: Object,
      required: true
    }
  },
  emits: ['update-project'],
  data() {
    return {
      projects: [],
      selectedProjectId: null,
      showForm: false,
      isNewProject: false,
      form: this.getEmptyForm(),
      listLoading: false,       // 프로젝트 목록 로딩
      loading: false,           // 저장 중
      testingConnection: false, // 연결 테스트 중
      loadingOverlay: false,    // 전역 오버레이
      loadingMessage: '처리 중...',
      loadingSubMessage: '',
      message: { type: '', text: '' }
    }
  },
  mounted() {
    this.loadProjects()
  },
  methods: {
    getEmptyForm() {
      return {
        project_id: '',
        project_name: '',
        db_config: {
          host: '',
          port: 5432,
          db_name: '',
          db_schema: '',
          user: '',
          pw: ''
        }
      }
    },

    async loadProjects() {
      this.listLoading = true
      try {
        const response = await getProjects()
        this.projects = response.projects || []
      } catch (error) {
        console.error('프로젝트 목록 조회 실패:', error)
      } finally {
        this.listLoading = false
      }
    },

    showNewForm() {
      this.selectedProjectId = null
      this.isNewProject = true
      this.form = this.getEmptyForm()
      this.showForm = true
      this.message = { type: '', text: '' }
    },

    async viewProject(projectId) {
      this.selectedProjectId = projectId
      this.isNewProject = false
      this.message = { type: '', text: '' }

      // 상세 조회 로딩 오버레이
      this.loadingOverlay = true
      this.loadingMessage = '프로젝트 정보 로딩 중...'
      this.loadingSubMessage = 'DB에서 데이터를 가져오고 있습니다'

      try {
        const response = await getProject(projectId)
        this.form = {
          project_id: response.project_id,
          project_name: response.project_name,
          db_config: {
            host: response.db_config.host,
            port: response.db_config.port,
            db_name: response.db_config.db_name,
            db_schema: response.db_config.db_schema || '',
            user: response.db_config.user,
            pw: response.db_config.pw // 백엔드에서 준 마스킹 값 (********) 적용
          }
        }
        this.showForm = true
      } catch (error) {
        this.message = { type: 'error', text: error.message }
      } finally {
        this.loadingOverlay = false
      }
    },

    handleSelectProject() {
      // 현재 폼의 프로젝트를 사용 프로젝트로 설정
      this.$emit('update-project', {
        project_id: this.form.project_id,
        project_name: this.form.project_name,
        db_config: this.form.db_config
      })
      this.message = { type: 'success', text: `'${this.form.project_name}' 프로젝트가 선택되었습니다.` }
    },

    handleDeselectProject() {
      // 프로젝트 선택 해제
      this.$emit('update-project', {
        project_id: '',
        project_name: '프로젝트 미설정',
        db_config: { host: '', port: 5432, db_name: '', user: '', pw: '' }
      })
      this.message = { type: 'success', text: '프로젝트 선택이 해제되었습니다.' }
    },

    cancelForm() {
      this.showForm = false
      this.selectedProjectId = null
      this.form = this.getEmptyForm()
      this.message = { type: '', text: '' }
    },

    async handleSubmit() {
      this.loading = true
      this.loadingOverlay = true
      this.loadingMessage = this.isNewProject ? '프로젝트 등록 중...' : '프로젝트 저장 중...'
      this.loadingSubMessage = 'DB에 연결하여 저장하고 있습니다'
      this.message = { type: '', text: '' }

      try {
        const response = await saveProject(this.form)
        this.message = { type: 'success', text: response.message }

        // 목록 새로고침
        await this.loadProjects()

        // 새 프로젝트면 상세 보기 모드로 변경
        if (this.isNewProject) {
          this.isNewProject = false
          this.selectedProjectId = this.form.project_id
        }
      } catch (error) {
        this.message = { type: 'error', text: error.message }
      } finally {
        this.loading = false
        this.loadingOverlay = false
      }
    },

    async handleDelete(projectId) {
      if (!confirm(`'${projectId}' 프로젝트를 삭제하시겠습니까?`)) {
        return
      }

      this.loadingOverlay = true
      this.loadingMessage = '프로젝트 삭제 중...'
      this.loadingSubMessage = ''

      try {
        await deleteProject(projectId)

        // 목록 새로고침
        await this.loadProjects()

        // 삭제된 프로젝트가 선택된 상태였으면 폼 닫기
        if (this.selectedProjectId === projectId) {
          this.cancelForm()
        }

        // 삭제된 프로젝트가 현재 프로젝트였으면 초기화
        if (this.project.project_id === projectId) {
          this.$emit('update-project', {
            project_id: '',
            project_name: '프로젝트 미설정',
            db_config: { host: '', port: 5432, db_name: '', user: '', pw: '' }
          })
        }
      } catch (error) {
        alert('삭제 실패: ' + error.message)
      } finally {
        this.loadingOverlay = false
      }
    },

    async handleTestConnection() {
      if (!this.form.project_id) {
        this.message = { type: 'error', text: '먼저 프로젝트를 저장해주세요.' }
        return
      }

      // 새 프로젝트인데 아직 저장하지 않은 경우
      if (this.isNewProject) {
        this.message = { type: 'error', text: '프로젝트를 먼저 등록한 후 연결 테스트를 진행해주세요.' }
        return
      }

      this.testingConnection = true
      this.message = { type: '', text: '' }

      try {
        // 화면의 입력값(this.form.db_config)을 전달하여 실시간 테스트
        const response = await testConnection(this.form.project_id || 'temp', this.form.db_config)

        if (response.connected) {
          this.message = { type: 'success', text: response.message }
        } else {
          this.message = { type: 'error', text: response.message }
        }
      } catch (error) {
        this.message = { type: 'error', text: error.message }
      } finally {
        this.testingConnection = false
      }
    }
  }
}
</script>

<style scoped>
.setting-view {
  max-width: 1000px;
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

.setting-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 24px;
}

/* ─── 스켈레톤 로딩 ─── */
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-item {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.skeleton-line {
  height: 12px;
  border-radius: 6px;
  background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}

.skeleton-line.long  { width: 75%; }
.skeleton-line.short { width: 45%; }

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ─── 버튼 인라인 스피너 ─── */
.btn-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}



/* 프로젝트 목록 */
.project-list-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  height: fit-content;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.project-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.project-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.project-item:hover {
  background: #e8edff;
}

.project-item.active {
  background: #e8edff;
  border-color: #667eea;
}

.project-item.current {
  background: #e8f5e9;
}

.project-item.current.active {
  background: #e8f5e9;
  border-color: #4caf50;
}

.current-badge {
  display: inline-block;
  font-size: 10px;
  padding: 2px 6px;
  background: #4caf50;
  color: white;
  border-radius: 4px;
  margin-left: 6px;
  font-weight: 500;
}

.project-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}

.project-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.project-id {
  font-size: 11px;
  color: #888;
  font-family: monospace;
}

.project-db {
  font-size: 11px;
  color: #666;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.btn-delete {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: #999;
  cursor: pointer;
  border-radius: 4px;
  font-size: 14px;
}

.btn-delete:hover {
  background: #ffebee;
  color: #c62828;
}

.empty-list {
  text-align: center;
  padding: 30px 20px;
  color: #888;
}

.empty-list p {
  margin-bottom: 16px;
}

/* 폼 섹션 */
.project-form-section {
  min-height: 400px;
}

.form-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eee;
}

.form-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.selected-badge {
  font-size: 12px;
  padding: 4px 10px;
  background: #4caf50;
  color: white;
  border-radius: 12px;
  font-weight: 500;
}

.project-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-label {
  font-size: 14px;
  font-weight: 600;
  color: #555;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-row {
  display: flex;
  gap: 12px;
}

.flex-1 {
  flex: 1;
}

.form-label {
  font-size: 13px;
  font-weight: 500;
  color: #555;
}

.form-input {
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-input:disabled {
  background: #f5f5f5;
  color: #888;
}

.form-hint {
  font-size: 12px;
  color: #888;
  margin-top: 2px;
}

.optional-label {
  font-size: 11px;
  color: #aaa;
  font-weight: 400;
}

.message {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
}

.message.success {
  background: #e8f5e9;
  color: #2e7d32;
}

.message.error {
  background: #ffebee;
  color: #c62828;
}

.form-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #eee;
}

.action-right {
  display: flex;
  gap: 8px;
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

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
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
  background: #e3f2fd;
  color: #1565c0;
}

.btn-secondary:hover {
  background: #bbdefb;
}

.btn-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-ghost {
  background: transparent;
  color: #666;
}

.btn-ghost:hover {
  background: #f5f5f5;
}

.select-actions {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #eee;
}

.btn-select {
  width: 100%;
  padding: 12px 20px;
  background: linear-gradient(135deg, #4caf50 0%, #2e7d32 100%);
  color: white;
  font-size: 15px;
}

.btn-select:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(76, 175, 80, 0.4);
}

.btn-deselect {
  width: 100%;
  padding: 12px 20px;
  background: #f5f5f5;
  color: #666;
  font-size: 14px;
  border: 1px solid #ddd;
}

.btn-deselect:hover {
  background: #eee;
}

.select-guide {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  color: #888;
}

.guide-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

@media (max-width: 768px) {
  .setting-layout {
    grid-template-columns: 1fr;
  }
}
</style>
