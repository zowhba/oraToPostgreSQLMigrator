<template>
  <div class="admin-view">
    <div class="page-header">
      <div>
        <h2 class="page-title">🛡️ 관리자</h2>
        <p class="page-desc">계정/권한 및 시스템 설정을 관리합니다.</p>
      </div>
    </div>

    <!-- ───────── 계정 관리 ───────── -->
    <div class="card">
      <div class="card-title">
        <span>👥 계정 관리</span>
        <span class="card-sub">계정을 생성하고 권한을 부여합니다. 비밀번호는 해시로만 저장됩니다.</span>
      </div>

      <!-- 계정 생성 -->
      <div class="create-form">
        <div class="form-row">
          <div class="form-field">
            <label>ID</label>
            <input v-model.trim="newUser.username" type="text" placeholder="영문/숫자 3~50자" class="input" />
          </div>
          <div class="form-field">
            <label>이름 (선택)</label>
            <input v-model.trim="newUser.display_name" type="text" placeholder="표시 이름" class="input" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label>비밀번호</label>
            <input v-model="newUser.password" type="password" placeholder="8자 이상, 영문+숫자" class="input" autocomplete="new-password" />
          </div>
          <div class="form-field">
            <label>권한</label>
            <select v-model="newUser.role" class="input">
              <option v-for="r in roles" :key="r.value" :value="r.value">{{ r.label }}</option>
            </select>
          </div>
        </div>
        <p class="role-hint">{{ roleDesc[newUser.role] }}</p>
        <div class="actions">
          <button class="primary-btn" @click="submitCreate" :disabled="creating || !canCreate">
            {{ creating ? '생성 중...' : '계정 생성' }}
          </button>
        </div>
      </div>

      <!-- 계정 목록 -->
      <div class="table-wrapper">
        <table class="user-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>이름</th>
              <th>권한</th>
              <th>상태</th>
              <th>최근 로그인</th>
              <th class="col-actions">관리</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.username" :class="{ inactive: !u.is_active }">
              <td class="mono">
                {{ u.username }}
                <span v-if="u.username === myUsername" class="me-chip">나</span>
              </td>
              <td>{{ u.display_name || '-' }}</td>
              <td>
                <select
                  :value="u.role"
                  class="role-select"
                  :disabled="u.username === myUsername"
                  @change="changeRole(u, $event.target.value)"
                >
                  <option v-for="r in roles" :key="r.value" :value="r.value">{{ r.label }}</option>
                </select>
              </td>
              <td>
                <span class="status-chip" :class="u.is_active ? 'on' : 'off'">
                  {{ u.is_active ? '활성' : '비활성' }}
                </span>
                <span v-if="u.must_change_pw" class="status-chip warn" title="최초 로그인 시 비밀번호 변경 필요">변경필요</span>
              </td>
              <td class="mono dim">{{ formatDate(u.last_login_at) }}</td>
              <td class="col-actions">
                <div class="row-actions">
                  <button class="mini-btn" @click="resetPassword(u)">비밀번호 초기화</button>
                  <button
                    class="mini-btn"
                    :disabled="u.username === myUsername"
                    @click="toggleActive(u)"
                  >{{ u.is_active ? '비활성화' : '활성화' }}</button>
                  <button
                    class="mini-btn danger"
                    :disabled="u.username === myUsername"
                    @click="removeUser(u)"
                  >삭제</button>
                </div>
              </td>
            </tr>
            <tr v-if="users.length === 0">
              <td colspan="6" class="empty">등록된 계정이 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 권한 설명 -->
      <div class="role-legend">
        <div v-for="r in roles" :key="r.value" class="legend-item">
          <span class="legend-chip" :class="'chip-' + r.value">{{ shortLabel(r.value) }}</span>
          <span class="legend-desc">{{ roleDesc[r.value] }}</span>
        </div>
      </div>
    </div>

    <!-- ───────── LLM 모델 활성화 ───────── -->
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

    <!-- ───────── 내 비밀번호 변경 ───────── -->
    <div class="card">
      <div class="card-title">
        <span>🔑 내 비밀번호 변경</span>
        <span class="card-sub">8자 이상, 영문과 숫자를 조합하세요.</span>
      </div>
      <div class="pw-form">
        <input v-model="oldPw" type="password" placeholder="기존 비밀번호" class="input" autocomplete="current-password" />
        <input v-model="newPw" type="password" placeholder="새 비밀번호" class="input" autocomplete="new-password" />
        <button class="primary-btn" @click="submitPasswordChange" :disabled="!oldPw || !newPw">변경</button>
      </div>
    </div>
  </div>
</template>

<script>
import {
  getEnabledModels, setEnabledModels,
  getUsers, createUser, updateUser, deleteUser, changeMyPassword
} from '../api'
import { auth, ROLE_ADMIN, ROLE_ACTOR, ROLE_VIEWER, ROLE_LABEL, ROLE_DESC } from '../auth'

export default {
  name: 'AdminView',
  data() {
    return {
      users: [],
      creating: false,
      newUser: { username: '', display_name: '', password: '', role: ROLE_VIEWER },
      roles: [
        { value: ROLE_ADMIN, label: 'Admin — 전체 관리' },
        { value: ROLE_ACTOR, label: 'Actor — 환경 조회 + 쿼리 변환' },
        { value: ROLE_VIEWER, label: 'Viewer — 이력 조회 전용' }
      ],
      roleDesc: ROLE_DESC,
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
  computed: {
    myUsername() {
      return auth.user ? auth.user.username : ''
    },
    canCreate() {
      return this.newUser.username && this.newUser.password && this.newUser.role
    }
  },
  async mounted() {
    await Promise.all([this.fetchUsers(), this.fetchEnabledModels()])
  },
  methods: {
    shortLabel(role) {
      return ROLE_LABEL[role] || role
    },
    formatDate(iso) {
      if (!iso) return '-'
      const d = new Date(iso)
      if (Number.isNaN(d.getTime())) return '-'
      const p = n => String(n).padStart(2, '0')
      return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
    },
    errText(e, fallback) {
      return e?.response?.data?.detail || e?.message || fallback
    },

    // ── 계정 관리 ──
    async fetchUsers() {
      try {
        const res = await getUsers()
        this.users = res.users || []
      } catch (e) {
        console.error('Failed to fetch users:', e)
      }
    },

    async submitCreate() {
      this.creating = true
      try {
        await createUser({
          username: this.newUser.username,
          password: this.newUser.password,
          role: this.newUser.role,
          display_name: this.newUser.display_name || null
        })
        alert(`계정 '${this.newUser.username}'이 생성되었습니다.\n최초 로그인 시 비밀번호 변경이 요구됩니다.`)
        this.newUser = { username: '', display_name: '', password: '', role: ROLE_VIEWER }
        await this.fetchUsers()
      } catch (e) {
        alert('계정 생성 실패: ' + this.errText(e, '알 수 없는 오류'))
      } finally {
        this.creating = false
      }
    },

    async changeRole(user, role) {
      if (role === user.role) return
      if (!confirm(`'${user.username}'의 권한을 ${this.shortLabel(role)}(으)로 변경하시겠습니까?`)) {
        await this.fetchUsers()
        return
      }
      try {
        await updateUser(user.username, { role })
        await this.fetchUsers()
      } catch (e) {
        alert('권한 변경 실패: ' + this.errText(e, '알 수 없는 오류'))
        await this.fetchUsers()
      }
    },

    async toggleActive(user) {
      const next = !user.is_active
      if (!confirm(`'${user.username}' 계정을 ${next ? '활성화' : '비활성화'}하시겠습니까?`)) return
      try {
        await updateUser(user.username, { is_active: next })
        await this.fetchUsers()
      } catch (e) {
        alert('상태 변경 실패: ' + this.errText(e, '알 수 없는 오류'))
      }
    },

    async resetPassword(user) {
      const pw = prompt(`'${user.username}'의 새 비밀번호를 입력하세요.\n(8자 이상, 영문+숫자 조합)`)
      if (!pw) return
      try {
        await updateUser(user.username, { new_password: pw })
        alert('비밀번호가 초기화되었습니다. 해당 사용자는 최초 로그인 시 변경해야 합니다.')
        await this.fetchUsers()
      } catch (e) {
        alert('초기화 실패: ' + this.errText(e, '알 수 없는 오류'))
      }
    },

    async removeUser(user) {
      if (!confirm(`'${user.username}' 계정을 삭제하시겠습니까? 되돌릴 수 없습니다.`)) return
      try {
        await deleteUser(user.username)
        await this.fetchUsers()
      } catch (e) {
        alert('삭제 실패: ' + this.errText(e, '알 수 없는 오류'))
      }
    },

    // ── 모델 활성화 ──
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
        alert('저장 실패: ' + this.errText(e, '알 수 없는 오류'))
      } finally {
        this.saving = false
      }
    },

    // ── 내 비밀번호 ──
    async submitPasswordChange() {
      try {
        await changeMyPassword(this.oldPw, this.newPw)
        alert('비밀번호가 변경되었습니다.')
        this.oldPw = ''
        this.newPw = ''
      } catch (e) {
        alert('변경 실패: ' + this.errText(e, '알 수 없는 오류'))
      }
    }
  }
}
</script>

<style scoped>
.admin-view {
  max-width: 960px;
  margin: 0 auto;
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

.page-desc { color: #7f8c8d; margin: 0; }

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

/* ── 계정 생성 폼 ── */
.create-form {
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 18px 20px;
  margin-bottom: 22px;
}

.form-row {
  display: flex;
  gap: 14px;
  margin-bottom: 12px;
}

.form-field {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.input {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  background: white;
  box-sizing: border-box;
  width: 100%;
}

.input:focus {
  outline: none;
  border-color: #6366f1;
}

.role-hint {
  font-size: 12px;
  color: #64748b;
  margin: 4px 0 12px;
}

.actions {
  display: flex;
  justify-content: flex-end;
}

.primary-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
}

.primary-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

/* ── 계정 테이블 ── */
.table-wrapper {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}

.user-table {
  width: 100%;
  border-collapse: collapse;
}

.user-table th {
  background: #f8fafc;
  text-align: left;
  padding: 11px 14px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}

.user-table td {
  padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
  color: #1e293b;
  vertical-align: middle;
}

.user-table tr:last-child td { border-bottom: none; }
.user-table tr.inactive { background: #fafafa; color: #94a3b8; }

.mono { font-family: 'Fira Code', 'Courier New', monospace; }
.dim { color: #94a3b8; font-size: 12px; }
.empty { text-align: center; color: #94a3b8; padding: 24px; }
.col-actions { width: 1%; white-space: nowrap; }

.me-chip {
  display: inline-block;
  margin-left: 6px;
  font-size: 10px;
  font-weight: 700;
  background: #e0e7ff;
  color: #4338ca;
  padding: 1px 6px;
  border-radius: 999px;
}

.role-select {
  padding: 5px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
  background: white;
  cursor: pointer;
}

.role-select:disabled {
  background: #f1f5f9;
  color: #94a3b8;
  cursor: not-allowed;
}

.status-chip {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  margin-right: 4px;
}

.status-chip.on { background: #dcfce7; color: #15803d; }
.status-chip.off { background: #f1f5f9; color: #64748b; }
.status-chip.warn { background: #fef3c7; color: #92400e; }

.row-actions {
  display: flex;
  gap: 6px;
}

.mini-btn {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #475569;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.mini-btn:hover:not(:disabled) { background: #e2e8f0; }

.mini-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.mini-btn.danger { color: #b91c1c; border-color: #fecaca; background: #fef2f2; }
.mini-btn.danger:hover:not(:disabled) { background: #fee2e2; }

/* ── 권한 설명 ── */
.role-legend {
  margin-top: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 10px;
  padding: 14px 18px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #0c4a6e;
}

.legend-chip {
  flex-shrink: 0;
  width: 58px;
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 0;
  border-radius: 999px;
}

.chip-admin { background: #fee2e2; color: #b91c1c; }
.chip-actor { background: #e0e7ff; color: #4338ca; }
.chip-viewer { background: #e2e8f0; color: #475569; }

/* ── 모델 목록 ── */
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

.model-name { font-weight: 600; color: #1e293b; }
.model-desc { font-size: 12px; color: #94a3b8; }

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

/* ── 비밀번호 폼 ── */
.pw-form {
  display: flex;
  gap: 10px;
  align-items: center;
}

.pw-form .input { flex: 1; }
</style>
