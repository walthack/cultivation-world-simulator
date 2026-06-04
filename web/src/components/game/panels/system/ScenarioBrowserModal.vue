<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NButton, NModal, NSpin, useMessage } from 'naive-ui'

import { ApiError } from '@/api/http'
import { useScenarioStore } from '@/stores/scenario'
import type { RepositoryScenarioDTO } from '@/types/api'
import ScenarioRepositoryTabs from './ScenarioRepositoryTabs.vue'
import ScenarioWizardModal from './ScenarioWizardModal.vue'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (event: 'update:show', value: boolean): void
  (event: 'select', scenarioId: string): void
}>()

const scenarioStore = useScenarioStore()
const message = useMessage()
const fileInput = ref<HTMLInputElement | null>(null)
const pendingConflictFile = ref<File | null>(null)
const conflictScenarioId = ref('')
const isDragActive = ref(false)
const isImporting = ref(false)
const showCreatorWizard = ref(false)
const activeTab = ref<'installed' | 'downloaded' | 'updates'>('installed')
const repositoryTabs = [
  { key: 'installed', label: 'Installed' },
  { key: 'downloaded', label: 'Downloaded' },
  { key: 'updates', label: 'Updates' },
] as const
const showConflictModal = computed(() => pendingConflictFile.value !== null)

function close() {
  emit('update:show', false)
}

function selectScenario(scenario: RepositoryScenarioDTO) {
  if (!scenario.enabled) return
  emit('select', scenario.id)
  close()
}

function openFilePicker() {
  fileInput.value?.click()
}

function openCreatorWizard() {
  showCreatorWizard.value = true
}

function extractConflictId(error: unknown): string {
  if (error instanceof ApiError) {
    const data = error.response.data as { detail?: { details?: { scenario_id?: string } } }
    return data.detail?.details?.scenario_id ?? ''
  }
  return ''
}

async function importFile(file: File, force = false, renameTo?: string) {
  isImporting.value = true
  try {
    await scenarioStore.importScenarioFile(file, { force, renameTo })
    message.success('Scenario imported')
    pendingConflictFile.value = null
    conflictScenarioId.value = ''
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      pendingConflictFile.value = file
      conflictScenarioId.value = extractConflictId(error)
      return
    }
    message.error(error instanceof Error ? error.message : 'Scenario import failed')
  } finally {
    isImporting.value = false
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    void importFile(file)
  }
  input.value = ''
}

function onDragEnter(event: DragEvent) {
  event.preventDefault()
  isDragActive.value = true
}

function onDragOver(event: DragEvent) {
  event.preventDefault()
  isDragActive.value = true
}

function onDragLeave(event: DragEvent) {
  if (event.currentTarget === event.target) {
    isDragActive.value = false
  }
}

function onDrop(event: DragEvent) {
  event.preventDefault()
  isDragActive.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) {
    void importFile(file)
  }
}

function cancelConflict() {
  pendingConflictFile.value = null
  conflictScenarioId.value = ''
}

function overwriteConflict() {
  const file = pendingConflictFile.value
  if (file) {
    void importFile(file, true)
  }
}

function renameConflict() {
  const nextId = window.prompt('New scenario id', conflictScenarioId.value)
  if (!nextId) return
  const file = pendingConflictFile.value
  if (file) {
    void importFile(file, false, nextId)
  }
}

async function onScenarioSaved() {
  await scenarioStore.fetchRepository()
}

watch(
  () => props.show,
  (isShown) => {
    if (isShown) {
      void scenarioStore.fetchRepository()
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
    <div
      class="scenario-drop-surface"
      :class="{ 'is-drag-active': isDragActive }"
      @dragenter="onDragEnter"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
    >
      <div class="scenario-browser-toolbar">
        <div class="scenario-browser-tabs" role="tablist" aria-label="Scenario repository tabs">
          <button
            v-for="tab in repositoryTabs"
            :key="tab.key"
            class="scenario-tab"
            :class="{ 'is-active': activeTab === tab.key }"
            type="button"
            role="tab"
            :aria-selected="activeTab === tab.key"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>
        <n-button size="small" @click="openCreatorWizard">
          Create Scenario
        </n-button>
        <n-button size="small" type="primary" :loading="isImporting" @click="openFilePicker">
          Import...
        </n-button>
        <input
          ref="fileInput"
          class="scenario-file-input"
          type="file"
          accept=".zip"
          @change="onFileChange"
        >
      </div>
      <div v-if="isDragActive" class="scenario-drop-overlay">Drop .zip to import</div>
    <n-spin :show="scenarioStore.isRepositoryLoading">
      <scenario-repository-tabs :active-tab="activeTab" @select="selectScenario" />
    </n-spin>
    </div>

    <template #footer>
      <div class="scenario-browser-footer">
        <n-button size="small" @click="close">关闭</n-button>
      </div>
    </template>
  </n-modal>

  <n-modal :show="showConflictModal" preset="card" title="Scenario already installed" class="scenario-conflict-modal">
    <p>Scenario {{ conflictScenarioId }} is already installed.</p>
    <template #footer>
      <div class="scenario-browser-footer">
        <n-button size="small" @click="cancelConflict">Cancel</n-button>
        <n-button size="small" @click="renameConflict">Rename</n-button>
        <n-button size="small" type="primary" @click="overwriteConflict">Overwrite</n-button>
      </div>
    </template>
  </n-modal>

  <scenario-wizard-modal
    v-if="showCreatorWizard"
    v-model:show="showCreatorWizard"
    @saved="onScenarioSaved"
  />
</template>

<style scoped>
.scenario-browser-modal {
  width: min(860px, calc(100vw - 32px));
}

.scenario-drop-surface {
  position: relative;
  min-height: 220px;
}

.scenario-browser-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.scenario-browser-tabs {
  display: flex;
  gap: 6px;
}

.scenario-tab {
  padding: 6px 10px;
  color: #d9d0c0;
  background: rgba(20, 22, 26, 0.9);
  border: 1px solid rgba(202, 164, 93, 0.22);
  border-radius: 6px;
  cursor: pointer;
}

.scenario-tab.is-active {
  color: #111;
  background: #f0cf86;
  border-color: #f0cf86;
}

.scenario-file-input {
  display: none;
}

.scenario-drop-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: grid;
  place-items: center;
  color: #f0cf86;
  font-weight: 600;
  background: rgba(12, 16, 20, 0.82);
  border: 1px dashed rgba(240, 207, 134, 0.8);
  border-radius: 8px;
  pointer-events: none;
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

.scenario-card.is-disabled {
  opacity: 0.58;
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

.scenario-card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
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

.scenario-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.scenario-browser-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.scenario-conflict-modal {
  width: min(420px, calc(100vw - 32px));
}
</style>
