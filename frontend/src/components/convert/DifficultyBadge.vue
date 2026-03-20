<template>
  <span :class="['badge', badgeClass]" :title="title">
    {{ label }}
  </span>
</template>

<script>
export default {
  name: "DifficultyBadge",
  props: {
    level: {
      type: [Number, String],
      required: true,
    },
  },
  computed: {
    normalizedLevel() {
      return Number(this.level);
    },
    badgeClass() {
      switch (this.normalizedLevel) {
        case 1:
          return "badge-success";
        case 2:
          return "badge-warning";
        case 3:
          return "badge-danger";
        default:
          return "badge-default";
      }
    },
    label() {
      switch (this.normalizedLevel) {
        case 1:
          return "Lv.1";
        case 2:
          return "Lv.2";
        case 3:
          return "Lv.3";
        default:
          return "-";
      }
    },
    title() {
      switch (this.normalizedLevel) {
        case 1:
          return "완전 자동 변환";
        case 2:
          return "AI 보정 필요";
        case 3:
          return "전문가 수동 검토";
        default:
          return "";
      }
    },
  },
};
</script>

<style scoped>
.badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.badge-success {
  background: #e8f5e9;
  color: #2e7d32;
}

.badge-warning {
  background: #fff3e0;
  color: #e65100;
}

.badge-danger {
  background: #ffebee;
  color: #c62828;
}

.badge-default {
  background: #f5f5f5;
  color: #757575;
}
</style>
