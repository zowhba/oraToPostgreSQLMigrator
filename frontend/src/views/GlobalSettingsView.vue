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
            v-for="model in visibleModels"
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
      <div class="form-group prompt-section">
        <label>
          전역 기본 시스템 프롬프트
          <span v-if="!isAdmin" class="readonly-badge">읽기 전용</span>
        </label>
        <p class="field-desc">새 프로젝트 생성 시 기본으로 사용되는 AI 지침입니다.{{ !isAdmin ? ' (편집은 Admin 모드에서만 가능)' : '' }}</p>
        <textarea
          v-model="globalSystemPrompt"
          placeholder="AI에게 전달할 기본 지침을 입력하세요..."
          rows="10"
          class="prompt-textarea"
          :class="{ 'readonly-field': !isAdmin }"
          :readonly="!isAdmin"
        ></textarea>
      </div>

      <!-- 과금 정책 관리 -->
      <div class="form-group pricing-section">
        <label>
          모델별 과금 정책
          <span v-if="!isAdmin" class="readonly-badge">읽기 전용</span>
        </label>
        <p class="field-desc">USD 기준 1M(백만) 토큰당 가격입니다. 비용 예측에 사용됩니다.{{ !isAdmin ? ' (편집은 Admin 모드에서만 가능)' : '' }}</p>
        <div class="pricing-table-wrapper">
          <table class="pricing-table">
            <thead>
              <tr>
                <th>모델</th>
                <th>입력 ($/1M tokens)</th>
                <th>출력 ($/1M tokens)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pricingList" :key="item.model_id">
                <td class="pricing-model-name">{{ item.display_name }}</td>
                <td>
                  <input
                    v-if="isAdmin"
                    type="number"
                    v-model.number="item.input_price"
                    step="0.01"
                    min="0"
                    class="pricing-input"
                  />
                  <span v-else class="pricing-value">${{ item.input_price }}</span>
                </td>
                <td>
                  <input
                    v-if="isAdmin"
                    type="number"
                    v-model.number="item.output_price"
                    step="0.01"
                    min="0"
                    class="pricing-input"
                  />
                  <span v-else class="pricing-value">${{ item.output_price }}</span>
                </td>
              </tr>
            </tbody>
          </table>
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
      isAdmin: false,
      activeModel: 'haiku-4.5',
      globalSystemPrompt: '',
      loading: false,
      pricingList: [],
      enabledModelIds: ['gpt-5.2-chat', 'haiku-4.5', 'sonnet-4.5', 'opus-4.6'],
      models: [
        { id: 'gpt-5.2-chat', name: 'Azure ChatGPT 5.2', desc: '기본 모델 (빠르고 안정적)' },
        { id: 'haiku-4.5', name: 'Claude 4.5 Haiku', desc: '매우 빠르고 지능적인 최신 경량 모델' },
        { id: 'sonnet-4.5', name: 'Claude 4.5 Sonnet', desc: '성능과 속도의 최적 밸런스 (추천)' },
        { id: 'opus-4.6', name: 'Claude 4.6 Opus', desc: '현존 최강의 추론 성능을 가진 프리미엄 모델' }
      ]
    }
  },
  computed: {
    visibleModels() {
      return this.models.filter(m => this.enabledModelIds.includes(m.id))
    }
  },
  methods: {
    async fetchSettings() {
      try {
        const response = await axios.get('/api/settings')
        if (response.data) {
          if (response.data.active_model) {
            this.activeModel = response.data.active_model
          }
          if (response.data.global_system_prompt) {
            this.globalSystemPrompt = response.data.global_system_prompt
          }
        }
      } catch (error) {
        console.error('Failed to fetch settings:', error)
      }
    },
    async fetchEnabledModels() {
      try {
        const response = await axios.get('/api/settings/enabled-models')
        if (response.data && Array.isArray(response.data.models)) {
          this.enabledModelIds = response.data.models
          // 현재 active 모델이 비활성화된 경우 첫 번째 활성 모델로 폴백
          if (!this.enabledModelIds.includes(this.activeModel) && this.enabledModelIds.length > 0) {
            this.activeModel = this.enabledModelIds[0]
          }
        }
      } catch (error) {
        console.error('Failed to fetch enabled models:', error)
      }
    },
    selectModel(modelId) {
      this.activeModel = modelId
    },
    async fetchPricing() {
      try {
        const response = await axios.get('/api/settings/pricing')
        if (response.data && response.data.pricing) {
          this.pricingList = response.data.pricing
        }
      } catch (error) {
        console.error('Failed to fetch pricing:', error)
      }
    },
    async saveSettings() {
      this.loading = true
      try {
        // 병렬 저장
        const promises = [
          axios.post('/api/settings', { key: 'active_model', value: this.activeModel })
        ]
        // 프롬프트, 과금 정책은 Admin만 저장
        if (this.isAdmin) {
          promises.push(axios.post('/api/settings', { key: 'global_system_prompt', value: this.globalSystemPrompt }))
          if (this.pricingList.length > 0) {
            promises.push(axios.post('/api/settings/pricing', { pricing: this.pricingList }))
          }
        }
        await Promise.all(promises)
        this.$emit('update-model')
        alert('모든 설정이 저장되었습니다.')
      } catch (error) {
        console.error('Failed to save settings:', error)
        alert('설정 저장에 실패했습니다.')
      } finally {
        this.loading = false
      }
    }
  },
  async mounted() {
    this.isAdmin = sessionStorage.getItem('sql_migrator_admin_authed') === '1'
    await this.fetchSettings()
    await this.fetchEnabledModels()
    await this.fetchPricing()
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

.field-desc {
  font-size: 13px;
  color: #888;
  margin-bottom: 10px;
}

.prompt-textarea {
  width: 100%;
  padding: 16px;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  font-family: 'Fira Code', 'Courier New', Courier, monospace;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  background: #fafafa;
}

.prompt-textarea:focus {
  outline: none;
  border-color: #667eea;
  background: #fff;
}

/* 과금 정책 테이블 */
.pricing-section {
  margin-top: 10px;
}

.pricing-table-wrapper {
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  overflow: hidden;
}

.pricing-table {
  width: 100%;
  border-collapse: collapse;
}

.pricing-table th {
  background: #f8fafc;
  text-align: left;
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  border-bottom: 1px solid #e2e8f0;
}

.pricing-table td {
  padding: 10px 16px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 14px;
}

.pricing-table tr:last-child td {
  border-bottom: none;
}

.pricing-model-name {
  font-weight: 600;
  color: #1e293b;
  min-width: 180px;
}

.pricing-input {
  width: 120px;
  padding: 6px 10px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 14px;
  font-family: 'Fira Code', monospace;
  text-align: right;
  background: #fafafa;
}

.pricing-input:focus {
  outline: none;
  border-color: #667eea;
  background: #fff;
}

.pricing-value {
  font-family: 'Fira Code', monospace;
  font-size: 14px;
  color: #475569;
}

.readonly-badge {
  display: inline-block;
  background: #f1f5f9;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 8px;
  vertical-align: middle;
}

.readonly-field {
  background: #f1f5f9 !important;
  color: #64748b !important;
  cursor: default;
}

.readonly-field:focus {
  border-color: #e0e0e0 !important;
  background: #f1f5f9 !important;
}
</style>
