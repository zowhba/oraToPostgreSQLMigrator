<template>
  <div class="global-settings">
    <div class="header">
      <h1>전역 설정</h1>
      <p>시스템 전역 설정을 관리합니다.</p>
    </div>

    <div class="settings-card">
      <div class="section-title">
        <span class="icon">🤖</span>
        LLM 모델 설정
      </div>
      
      <div class="form-group">
        <label>활성 AI 모델</label>
        <div class="model-selector">
          <div 
            v-for="model in models" 
            :key="model.id"
            class="model-option"
            :class="{ active: activeModel === model.id }"
            @click="selectModel(model.id)"
          >
            <div class="model-info">
              <span class="model-name">{{ model.name }}</span>
              <span class="model-desc">{{ model.desc }}</span>
            </div>
            <div class="radio-check" v-if="activeModel === model.id">✓</div>
          </div>
        </div>
      </div>

      <div class="actions">
        <button class="save-btn" @click="saveSettings" :disabled="loading">
          {{ loading ? '저장 중...' : '설정 저장' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'GlobalSettingsView',
  data() {
    return {
      activeModel: 'gpt-5.2-chat',
      loading: false,
      models: [
        { id: 'gpt-5.2-chat', name: 'Azure ChatGPT 5.2', desc: '기본 모델 (빠르고 안정적)' },
        { id: 'haiku-4.5', name: 'Claude 4.5 Haiku', desc: '매우 빠르고 지능적인 최신 경량 모델' },
        { id: 'sonnet-4.5', name: 'Claude 4.5 Sonnet', desc: '성능과 속도의 최적 밸런스 (추천)' },
        { id: 'opus-4.6', name: 'Claude 4.6 Opus', desc: '현존 최강의 추론 성능을 가진 프리미엄 모델' }
      ]
    }
  },
  methods: {
    async fetchActiveModel() {
      try {
        const response = await axios.get('http://localhost:8000/api/settings/active-model')
        if (response.data && response.data.active_model) {
          this.activeModel = response.data.active_model
        }
      } catch (error) {
        console.error('Failed to fetch active model:', error)
      }
    },
    selectModel(modelId) {
      this.activeModel = modelId
    },
    async saveSettings() {
      this.loading = true
      try {
        await axios.post('http://localhost:8000/api/settings', {
          key: 'active_model',
          value: this.activeModel
        })
        alert('설정이 저장되었습니다.')
      } catch (error) {
        console.error('Failed to save settings:', error)
        alert('설정 저장에 실패했습니다.')
      } finally {
        this.loading = false
      }
    }
  },
  mounted() {
    this.fetchActiveModel()
  }
}
</script>

<style scoped>
.global-settings {
  max-width: 800px;
  margin: 0 auto;
}

.header {
  margin-bottom: 30px;
}

.header h1 {
  font-size: 24px;
  color: #333;
  margin-bottom: 8px;
}

.header p {
  color: #666;
}

.settings-card {
  background: white;
  border-radius: 12px;
  padding: 32px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.05);
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #1a1a2e;
}

.form-group {
  margin-bottom: 30px;
}

.form-group label {
  display: block;
  font-weight: 500;
  margin-bottom: 12px;
  color: #555;
}

.model-selector {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.model-option {
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  padding: 16px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.2s;
}

.model-option:hover {
  border-color: #667eea;
  background: #f8faff;
}

.model-option.active {
  border-color: #667eea;
  background: #f0f4ff;
  border-width: 2px;
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-name {
  font-weight: 600;
  color: #1a1a2e;
}

.model-desc {
  font-size: 12px;
  color: #777;
}

.radio-check {
  color: #667eea;
  font-weight: bold;
  font-size: 18px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #eee;
  padding-top: 24px;
}

.save-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.1s;
}

.save-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.save-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
  transform: none;
}
</style>
