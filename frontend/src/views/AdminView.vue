<template>
  <div class="admin-view">
    <!-- 패스워드 게이트 -->
    <div v-if="!authenticated" class="login-card">
      <div class="login-icon">🔐</div>
      <h2>관리자 인증</h2>
      <p class="login-desc">Admin 모드에 진입하려면 패스워드를 입력하세요.</p>
      <form @submit.prevent="login">
        <input
          ref="pwInput"
          v-model="password"
          type="password"
          placeholder="패스워드"
          class="pw-input"
          :disabled="loading"
        />
        <button type="submit" class="login-btn" :disabled="loading || !password">
          {{ loading ? '확인 중...' : '입장' }}
        </button>
      </form>
      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
    </div>

    <!-- Admin 패널 -->
    <div v-else>
      <div class="page-header">
        <div>
          <h2 class="page-title">🛡️ 관리자 모드</h2>
          <p class="page-desc">시스템 관리 전용 기능입니다.</p>
        </div>
        <button class="logout-btn" @click="logout">로그아웃</button>
      </div>

      <!-- LLM 모델 활성화 토글 -->
      <div class="card">
        <div class="card-title">
          <span>🤖 LLM 모델 활성화</span>
          <span class="card-sub">비활성화된 모델은 일반 사용자에게 노출되지 않습니다.</span>
        </div>
        <div class="model-list">
          <div v-for="model in allModels" :key="model.id" class="model-row">
            <div class="model-meta">
              <span class="model-name">{{ model.name }}</span>
              <span class="model-desc">{{ model.desc }}</span>
            </div>
            <label class="switch">
              <input
                type="checkbox"
                :checked="enabledModels.includes(model.id)"
                @change="toggleModel(model.id, $event.target.checked)"
              />
              <span class="slider"></span>
            </label>
          </div>
        </div>
        <div class="actions">
          <button class="primary-btn" @click="saveEnabledModels" :disabled="saving">
            {{ saving ? '저장 중...' : '활성화 설정 저장' }}
          </button>
        </div>
      </div>

      <!-- 패스워드 변경 -->
      <div class="card">
        <div class="card-title">
          <span>🔑 관리자 패스워드 변경</span>
        </div>
        <div class="pw-form">
          <input v-model="oldPw" type="password" placeholder="기존 패스워드" class="pw-input small" />
          <input v-model="newPw" type="password" placeholder="새 패스워드 (4자 이상)" class="pw-input small" />
          <button class="primary-btn" @click="changePassword" :disabled="!oldPw || !newPw">변경</button>
        </div>
      </div>

      <!-- 안내 -->
      <div class="info-card">
        <p>📌 Admin 모드에서는 <strong>작업 히스토리</strong> 메뉴에서 삭제 버튼이 활성화됩니다.</p>
        <p>📌 일반 모드에서는 삭제 버튼이 비활성화되어 있습니다.</p>
      </div>
    </div>
  </div>
</template>

<script>
import { adminLogin, changeAdminPassword, getEnabledModels, setEnabledModels } from '../api'

const ADMIN_FLAG_KEY = 'sql_migrator_admin_authed'

export default {
  name: 'AdminView',
  data() {
    return {
      authenticated: false,
      password: '',
      loading: false,
      errorMsg: '',
      saving: false,
      oldPw: '',
      newPw: '',
      enabledModels: [],
      allModels: [
        { id: 'gpt-5.2-chat', name: 'Azure ChatGPT 5.2', desc: '기본 모델 (빠르고 안정적)' },
        { id: 'haiku-4.5', name: 'Claude 4.5 Haiku', desc: '매우 빠르고 지능적인 최신 경량 모델' },
        { id: 'sonnet-4.5', name: 'Claude 4.5 Sonnet', desc: '성능과 속도의 최적 밸런스 (추천)' },
        { id: 'opus-4.6', name: 'Claude 4.6 Opus', desc: '현존 최강의 추론 성능을 가진 프리미엄 모델' }
      ]
    }
  },
  mounted() {
    this.authenticated = sessionStorage.getItem(ADMIN_FLAG_KEY) === '1'
    if (this.authenticated) {
      this.fetchEnabledModels()
    } else {
      this.$nextTick(() => this.$refs.pwInput && this.$refs.pwInput.focus())
    }
  },
  methods: {
    async login() {
      this.errorMsg = ''
      this.loading = true
      try {
        const res = await adminLogin(this.password)
        if (res.ok) {
          sessionStorage.setItem(ADMIN_FLAG_KEY, '1')
          window.dispatchEvent(new Event('admin-auth-changed'))
          this.authenticated = true
          this.password = ''
          await this.fetchEnabledModels()
        } else {
          this.errorMsg = res.message || '패스워드가 일치하지 않습니다.'
        }
      } catch (e) {
        this.errorMsg = '인증 중 오류가 발생했습니다.'
      } finally {
        this.loading = false
      }
    },
    logout() {
      sessionStorage.removeItem(ADMIN_FLAG_KEY)
      window.dispatchEvent(new Event('admin-auth-changed'))
      this.authenticated = false
    },
    async fetchEnabledModels() {
      try {
        const res = await getEnabledModels()
        this.enabledModels = res.models || []
      } catch (e) {
        console.error('Failed to fetch enabled models:', e)
      }
    },
    toggleModel(id, checked) {
      if (checked) {
        if (!this.enabledModels.includes(id)) this.enabledModels.push(id)
      } else {
        this.enabledModels = this.enabledModels.filter(m => m !== id)
      }
    },
    async saveEnabledModels() {
      if (this.enabledModels.length === 0) {
        alert('최소 1개 이상의 모델은 활성화되어야 합니다.')
        return
      }
      this.saving = true
      try {
        await setEnabledModels(this.enabledModels)
        alert('활성화 설정이 저장되었습니다.')
      } catch (e) {
        alert('저장 실패: ' + (e?.response?.data?.detail || e.message))
      } finally {
        this.saving = false
      }
    },
    async changePassword() {
      if (this.newPw.length < 4) {
        alert('새 패스워드는 4자 이상이어야 합니다.')
        return
      }
      try {
        await changeAdminPassword(this.oldPw, this.newPw)
        alert('패스워드가 변경되었습니다.')
        this.oldPw = ''
        this.newPw = ''
      } catch (e) {
        alert('변경 실패: ' + (e?.response?.data?.detail || e.message))
      }
    }
  }
}
</script>

<style scoped>
.admin-view {
  max-width: 800px;
  margin: 0 auto;
}

.login-card {
  max-width: 420px;
  margin: 80px auto;
  background: white;
  border-radius: 14px;
  padding: 40px 32px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  text-align: center;
}

.login-icon { font-size: 44px; margin-bottom: 12px; }

.login-card h2 {
  margin: 0 0 8px;
  color: #1e293b;
}

.login-desc {
  color: #64748b;
  margin-bottom: 24px;
  font-size: 14px;
}

.pw-input {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 15px;
  margin-bottom: 12px;
  box-sizing: border-box;
}

.pw-input:focus {
  outline: none;
  border-color: #6366f1;
}

.pw-input.small {
  margin-bottom: 0;
  flex: 1;
}

.login-btn, .primary-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 12px 22px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  width: 100%;
  font-size: 15px;
}

.primary-btn {
  width: auto;
}

.login-btn:disabled, .primary-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.error-msg {
  color: #dc2626;
  margin-top: 14px;
  font-size: 13px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: #2c3e50;
  margin: 0 0 4px;
}

.page-desc { color: #7f8c8d; }

.logout-btn {
  background: #f1f5f9;
  border: none;
  color: #475569;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
}

.logout-btn:hover { background: #e2e8f0; }

.card {
  background: white;
  border-radius: 12px;
  padding: 24px 28px;
  margin-bottom: 20px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
}

.card-title {
  font-size: 17px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-sub {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 400;
}

.model-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 18px;
}

.model-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border: 1px solid #edf2f7;
  border-radius: 10px;
}

.model-meta {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.model-name {
  font-weight: 600;
  color: #1e293b;
}

.model-desc {
  font-size: 12px;
  color: #94a3b8;
}

/* Toggle switch */
.switch {
  position: relative;
  display: inline-block;
  width: 46px;
  height: 26px;
}

.switch input { opacity: 0; width: 0; height: 0; }

.slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background: #cbd5e1;
  border-radius: 999px;
  transition: 0.2s;
}

.slider:before {
  position: absolute;
  content: "";
  height: 20px; width: 20px;
  left: 3px; bottom: 3px;
  background: white;
  border-radius: 50%;
  transition: 0.2s;
}

.switch input:checked + .slider { background: #6366f1; }
.switch input:checked + .slider:before { transform: translateX(20px); }

.actions {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #f1f5f9;
  padding-top: 16px;
}

.pw-form {
  display: flex;
  gap: 10px;
  align-items: center;
}

.info-card {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 10px;
  padding: 16px 20px;
  color: #0c4a6e;
  font-size: 13px;
}

.info-card p { margin: 4px 0; }
</style>
