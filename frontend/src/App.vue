<template>
  <!-- 로그인 등 인증 전 화면은 헤더/사이드바 없이 표시 -->
  <router-view v-if="isBlankLayout" />

  <div v-else class="app-container">
    <AppHeader
      :projectName="currentProject.project_name"
      :activeModelName="activeModelLabel"
    />
    <div class="app-body">
      <AppSidebar />
      <main class="app-main">
        <router-view
          :project="currentProject"
          @update-project="updateProject"
          @update-model="fetchActiveModel"
        />
      </main>
    </div>
  </div>
</template>

<script>
import AppHeader from './components/layout/AppHeader.vue'
import AppSidebar from './components/layout/AppSidebar.vue'
import axios from 'axios'
import { isLoggedIn } from './auth'

export default {
  name: 'App',
  components: {
    AppHeader,
    AppSidebar
  },
  data() {
    return {
      currentProject: {
        project_id: '',
        project_name: '프로젝트 미설정',
        db_config: {
          host: '',
          port: 5432,
          db_name: '',
          user: '',
          pw: ''
        }
      },
      activeModel: '',
      modelMapping: {
        'gpt-5.2-chat': 'Azure GPT 5.2',
        'haiku-4.5': 'Claude 4.5 Haiku',
        'sonnet-4.5': 'Claude 4.5 Sonnet',
        'opus-4.6': 'Claude 4.6 Opus'
      }
    }
  },
  computed: {
    activeModelLabel() {
      return this.modelMapping[this.activeModel] || this.activeModel
    },
    isBlankLayout() {
      return this.$route.meta && this.$route.meta.layout === 'blank'
    }
  },
  watch: {
    // 로그인 직후 헤더 정보를 채운다
    $route() {
      if (!this.isBlankLayout && !this.activeModel) {
        this.fetchActiveModel()
      }
    }
  },
  methods: {
    updateProject(project) {
      this.currentProject = project
      localStorage.setItem('currentProject', JSON.stringify(project))
    },
    async fetchActiveModel() {
      if (!isLoggedIn()) return
      try {
        const response = await axios.get('/api/settings/active-model')
        if (response.data && response.data.active_model) {
          this.activeModel = response.data.active_model
        }
      } catch (error) {
        console.error('Failed to fetch active model:', error)
      }
    }
  },
  mounted() {
    const saved = localStorage.getItem('currentProject')
    if (saved) {
      this.currentProject = JSON.parse(saved)
    }
    this.fetchActiveModel()
  }
}
</script>

<style>
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-body {
  display: flex;
  flex: 1;
}

.app-main {
  flex: 1;
  padding: 24px;
  background-color: #f5f5f5;
  overflow-y: auto;
}
</style>
