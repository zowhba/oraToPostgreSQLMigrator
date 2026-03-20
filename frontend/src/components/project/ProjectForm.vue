<template>
  <form @submit.prevent="handleSubmit" class="project-form">
    <!-- 프로젝트 정보 -->
    <div class="form-section">
      <h3 class="section-title">프로젝트 정보</h3>

      <div class="form-group">
        <label class="form-label">프로젝트 ID</label>
        <input
          type="text"
          v-model="form.project_id"
          class="form-input"
          placeholder="예: PRJ_SKB_001"
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
      <h3 class="section-title">PostgreSQL 접속 정보</h3>

      <div class="form-row">
        <div class="form-group">
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

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">사용자</label>
          <input
            type="text"
            v-model="form.db_config.user"
            class="form-input"
            placeholder="예: migrator"
            required
          />
        </div>

        <div class="form-group">
          <label class="form-label">비밀번호</label>
          <input
            type="password"
            v-model="form.db_config.pw"
            class="form-input"
            placeholder="비밀번호 입력"
            required
          />
        </div>
      </div>
    </div>

    <!-- 메시지 -->
    <div v-if="message.text" :class="['message', message.type]">
      {{ message.text }}
    </div>

    <!-- 저장 버튼 -->
    <button type="submit" class="btn btn-primary" :disabled="loading">
      {{ loading ? '저장 중...' : '설정 저장' }}
    </button>
  </form>
</template>

<script>
export default {
  name: 'ProjectForm',
  props: {
    project: {
      type: Object,
      required: true
    },
    loading: {
      type: Boolean,
      default: false
    },
    message: {
      type: Object,
      default: () => ({ type: '', text: '' })
    }
  },
  emits: ['submit'],
  data() {
    return {
      form: {
        project_id: '',
        project_name: '',
        db_config: {
          host: '',
          port: 5432,
          db_name: '',
          user: '',
          pw: ''
        }
      }
    }
  },
  watch: {
    project: {
      immediate: true,
      handler(val) {
        if (val) {
          this.form = JSON.parse(JSON.stringify(val))
        }
      }
    }
  },
  methods: {
    handleSubmit() {
      this.$emit('submit', this.form)
    }
  }
}
</script>

<style scoped>
.project-form {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-label {
  font-size: 14px;
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

.message {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
}

.message.success {
  background: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.message.error {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.btn {
  padding: 12px 24px;
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
}
</style>
