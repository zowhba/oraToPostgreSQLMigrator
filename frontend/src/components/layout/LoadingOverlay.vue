<template>
  <Teleport to="body">
    <Transition name="overlay-fade">
      <div v-if="visible" class="loading-overlay" role="status" aria-label="로딩 중">
        <div class="loading-box">
          <div class="spinner-ring">
            <div></div><div></div><div></div><div></div>
          </div>
          <p class="loading-msg">{{ message }}</p>
          <p v-if="subMessage" class="loading-sub">{{ subMessage }}</p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script>
export default {
  name: 'LoadingOverlay',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    message: {
      type: String,
      default: '로딩 중...'
    },
    subMessage: {
      type: String,
      default: ''
    }
  }
}
</script>

<style scoped>
.loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.loading-box {
  background: #fff;
  border-radius: 16px;
  padding: 36px 48px;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
  min-width: 220px;
}

/* 링 스피너 */
.spinner-ring {
  display: inline-block;
  position: relative;
  width: 56px;
  height: 56px;
  margin-bottom: 18px;
}

.spinner-ring div {
  box-sizing: border-box;
  display: block;
  position: absolute;
  width: 44px;
  height: 44px;
  margin: 6px;
  border: 4px solid transparent;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

.spinner-ring div:nth-child(1) { animation-delay: -0.45s; border-top-color: #667eea; }
.spinner-ring div:nth-child(2) { animation-delay: -0.3s;  border-top-color: #764ba2; }
.spinner-ring div:nth-child(3) { animation-delay: -0.15s; border-top-color: #667eea; opacity: 0.6; }
.spinner-ring div:nth-child(4) { animation-delay: 0s;     border-top-color: #764ba2; opacity: 0.3; }

@keyframes spin {
  0%   { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-msg {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 6px;
}

.loading-sub {
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
  line-height: 1.5;
}

/* 전환 애니메이션 */
.overlay-fade-enter-active,
.overlay-fade-leave-active {
  transition: opacity 0.2s ease;
}

.overlay-fade-enter-active .loading-box,
.overlay-fade-leave-active .loading-box {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
}

.overlay-fade-enter-from .loading-box,
.overlay-fade-leave-to .loading-box {
  transform: scale(0.92);
  opacity: 0;
}
</style>
