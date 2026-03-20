<template>
  <div class="app-container">
    <AppHeader :projectName="currentProject.project_name" />
    <div class="app-body">
      <AppSidebar />
      <main class="app-main">
        <router-view
          :project="currentProject"
          @update-project="updateProject"
        />
      </main>
    </div>
  </div>
</template>

<script>
import AppHeader from './components/layout/AppHeader.vue'
import AppSidebar from './components/layout/AppSidebar.vue'

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
      }
    }
  },
  methods: {
    updateProject(project) {
      this.currentProject = project
      localStorage.setItem('currentProject', JSON.stringify(project))
    }
  },
  mounted() {
    const saved = localStorage.getItem('currentProject')
    if (saved) {
      this.currentProject = JSON.parse(saved)
    }
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
