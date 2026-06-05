<script setup lang="ts">
import { useScenarioStore } from '@/stores/scenario'
import scrollIcon from '@/assets/icons/ui/lucide/scroll-text.svg'

const emit = defineEmits<{
  (e: 'open'): void;
}>()

const scenarioStore = useScenarioStore()
</script>

<template>
  <button
    v-if="scenarioStore.status.active"
    class="scenario-badge"
    type="button"
    title="查看剧本"
    @click="emit('open')"
  >
    <span class="scenario-badge-icon" :style="{ '--icon-url': `url(${scrollIcon})` }" aria-hidden="true"></span>
    <span class="scenario-badge-title">{{ scenarioStore.status.title }}</span>
  </button>
</template>

<style scoped>
.scenario-badge {
  height: 40px;
  max-width: 220px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 12px;
  border: 1px solid rgba(202, 164, 93, 0.34);
  border-radius: 4px;
  color: #f3d79c;
  background: rgba(39, 28, 12, 0.72);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.22);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, color 0.2s;
}

.scenario-badge:hover {
  border-color: rgba(240, 207, 134, 0.58);
  background: rgba(54, 38, 14, 0.84);
  color: #fff0c8;
}

.scenario-badge-icon {
  width: 17px;
  height: 17px;
  flex: 0 0 auto;
  display: inline-block;
  background-color: currentColor;
  -webkit-mask-image: var(--icon-url);
  mask-image: var(--icon-url);
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center;
  mask-position: center;
  -webkit-mask-size: contain;
  mask-size: contain;
}

.scenario-badge-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  line-height: 1;
  font-weight: 700;
}
</style>
