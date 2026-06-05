<script setup lang="ts">
import { watch } from 'vue'
import { NButton, NEmpty, NModal, NSpin, NTag } from 'naive-ui'

import { useScenarioStore } from '@/stores/scenario'
import type { InstalledScenarioMeta } from '@/types/api'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (event: 'update:show', value: boolean): void
  (event: 'select', scenarioId: string): void
}>()

const scenarioStore = useScenarioStore()

function close() {
  emit('update:show', false)
}

function selectScenario(scenario: InstalledScenarioMeta) {
  emit('select', scenario.id)
  close()
}

watch(
  () => props.show,
  (isShown) => {
    if (isShown) {
      void scenarioStore.fetchInstalledScenarios()
    }
  },
  { immediate: true },
)
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="Scenario Browser"
    class="scenario-browser-modal"
    @update:show="(value: boolean) => emit('update:show', value)"
  >
    <n-spin :show="scenarioStore.isInstalledLoading">
      <div v-if="scenarioStore.installedScenarios.length" class="scenario-grid">
        <button
          v-for="scenario in scenarioStore.installedScenarios"
          :key="scenario.id"
          class="scenario-card"
          type="button"
          @click="selectScenario(scenario)"
        >
          <img
            v-if="scenario.cover_image"
            class="scenario-cover"
            :src="scenario.cover_image"
            :alt="scenario.name"
          >
          <div class="scenario-card-body">
            <div class="scenario-card-header">
              <h4>{{ scenario.name }}</h4>
              <span class="scenario-version">v{{ scenario.version }}</span>
            </div>
            <div v-if="scenario.author" class="scenario-author">{{ scenario.author }}</div>
            <p>{{ scenario.description }}</p>
            <div v-if="scenario.tags.length" class="scenario-tags">
              <n-tag
                v-for="tag in scenario.tags"
                :key="tag"
                size="small"
                :bordered="false"
              >
                {{ tag }}
              </n-tag>
            </div>
          </div>
        </button>
      </div>
      <n-empty v-else description="未发现可用 scenario" />
    </n-spin>

    <template #footer>
      <div class="scenario-browser-footer">
        <n-button size="small" @click="close">关闭</n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.scenario-browser-modal {
  width: min(860px, calc(100vw - 32px));
}

.scenario-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
}

.scenario-card {
  display: flex;
  gap: 12px;
  min-height: 142px;
  padding: 14px;
  color: #eee;
  text-align: left;
  background: rgba(22, 24, 28, 0.92);
  border: 1px solid rgba(202, 164, 93, 0.26);
  border-radius: 8px;
  cursor: pointer;
}

.scenario-card:hover {
  border-color: rgba(240, 207, 134, 0.7);
  background: rgba(34, 32, 28, 0.95);
}

.scenario-cover {
  width: 76px;
  height: 104px;
  object-fit: cover;
  border-radius: 6px;
  background: #111;
}

.scenario-card-body {
  min-width: 0;
  flex: 1;
}

.scenario-card-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.scenario-card h4 {
  margin: 0;
  color: #f0cf86;
  font-size: 1rem;
  line-height: 1.25;
}

.scenario-version,
.scenario-author,
.scenario-card p {
  color: #aaa;
  font-size: 0.85rem;
}

.scenario-card p {
  margin: 8px 0;
  line-height: 1.45;
}

.scenario-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.scenario-browser-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
