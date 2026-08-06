<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <div class="brand-icon">⇄</div>
        <h1 class="brand-title">AI 쿼리 변환 시스템</h1>
        <p class="brand-sub">Oracle → PostgreSQL Migration</p>
      </div>

      <!-- 로그인 폼 -->
      <form v-if="!mustChangePw" @submit.prevent="submit" class="form">
        <label class="field-label" for="login-username">ID</label>
        <input
          id="login-username"
          ref="usernameInput"
          v-model.trim="username"
          type="text"
          class="field"
          autocomplete="username"
          placeholder="사용자 ID"
          :disabled="loading"
        />

        <label class="field-label" for="login-password">비밀번호</label>
        <input
          id="login-password"
          v-model="password"
          type="password"
          class="field"
          autocomplete="current-password"
          placeholder="비밀번호"
          :disabled="loading"
        />

        <button type="submit" class="submit-btn" :disabled="loading || !username || !password">
          {{ loading ? '로그인 중...' : '로그인' }}
        </button>
      </form>

      <!-- 최초 로그인 시 비밀번호 변경 -->
      <form v-else @submit.prevent="submitPasswordChange" class="form">
        <div class="notice">
          보안을 위해 비밀번호를 변경해야 합니다.<br />
          8자 이상, 영문과 숫자를 조합하세요.
        </div>

        <label class="field-label" for="new-pw">새 비밀번호</label>
        <input id="new-pw" v-model="newPw" type="password" class="field"
               autocomplete="new-password" placeholder="새 비밀번호" :disabled="loading" />

        <label class="field-label" for="new-pw2">새 비밀번호 확인</label>
        <input id="new-pw2" v-model="newPw2" type="password" class="field"
               autocomplete="new-password" placeholder="새 비밀번호 확인" :disabled="loading" />

        <button type="submit" class="submit-btn" :disabled="loading || !newPw || !newPw2">
          {{ loading ? '변경 중...' : '비밀번호 변경 후 계속' }}
        </button>
      </form>

      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
    </div>
  </div>
</template>

<script>
import { login, changeMyPassword, fetchMe } from '../api'
import { setSession, clearSession, auth } from '../auth'

export default {
  name: 'LoginView',
  data() {
    return {
      username: '',
      password: '',
      newPw: '',
      newPw2: '',
      loading: false,
      errorMsg: '',
      mustChangePw: false
    }
  },
  mounted() {
    this.$nextTick(() => this.$refs.usernameInput && this.$refs.usernameInput.focus())
  },
  methods: {
    async submit() {
      this.errorMsg = ''
      this.loading = true
      try {
        const res = await login(this.username, this.password)
        setSession(res.access_token, res.user)
        if (res.user.must_change_pw) {
          this.mustChangePw = true
        } else {
          this.goNext()
        }
      } catch (e) {
        this.errorMsg = e?.response?.data?.detail || '로그인에 실패했습니다.'
      } finally {
        this.loading = false
      }
    },

    async submitPasswordChange() {
      this.errorMsg = ''
      if (this.newPw !== this.newPw2) {
        this.errorMsg = '새 비밀번호가 일치하지 않습니다.'
        return
      }
      this.loading = true
      try {
        await changeMyPassword(this.password, this.newPw)
        // 변경된 계정 정보로 세션 갱신
        const me = await fetchMe()
        setSession(auth.token, { ...me.user, must_change_pw: false })
        this.goNext()
      } catch (e) {
        this.errorMsg = e?.response?.data?.detail || '비밀번호 변경에 실패했습니다.'
      } finally {
        this.loading = false
      }
    },

    goNext() {
      const redirect = this.$route.query.redirect
      const fallback = auth.user && auth.user.role === 'viewer' ? '/history' : '/convert'
      this.$router.replace(redirect && redirect.startsWith('/') ? redirect : fallback)
    }
  },
  beforeRouteEnter(to, from, next) {
    // 로그인 화면 진입 시 잔여 세션 정리 (만료 토큰으로 인한 혼선 방지)
    clearSession()
    next()
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a2e 0%, #2d2d5a 100%);
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: white;
  border-radius: 16px;
  padding: 40px 36px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
}

.brand {
  text-align: center;
  margin-bottom: 28px;
}

.brand-icon {
  font-size: 34px;
  color: #667eea;
  margin-bottom: 8px;
}

.brand-title {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 4px;
}

.brand-sub {
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
  letter-spacing: 0.5px;
}

.form {
  display: flex;
  flex-direction: column;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 6px;
}

.field {
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 15px;
  margin-bottom: 16px;
  box-sizing: border-box;
}

.field:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.12);
}

.submit-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 13px 20px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 4px;
}

.submit-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.notice {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 18px;
}

.error-msg {
  color: #dc2626;
  font-size: 13px;
  text-align: center;
  margin: 16px 0 0;
}
</style>
