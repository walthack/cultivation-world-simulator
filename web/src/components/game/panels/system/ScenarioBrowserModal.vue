<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NButton, NEmpty, NModal, NSpin, NTag, useMessage } from 'naive-ui'

import { ApiError } from '@/api/http'
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
const message = useMessage()
const fileInput = ref<HTMLInputElement | null>(null)
const pendingConflictFile = ref<File | null>(null)
const conflictScenarioId = ref('')
const isDragActive = ref(false)
const isImporting = ref(false)
const showConflictModal = computed(() => pendingConflictFile.value !== null)

function close() {
  emit('update:show', false)
}

function selectScenario(scenario: InstalledScenarioMeta) {
  if (!scenario.enabled) return
  emit('select', scenario.id)
  close()
}

function openFilePicker() {
  fileInput.value?.click()
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

async function toggleScenario(scenario: InstalledScenarioMeta) {
  await scenarioStore.setScenarioEnabled(scenario.id, !scenario.enabled)
}

async function removeScenario(scenario: InstalledScenarioMeta) {
  await scenarioStore.removeScenario(scenario.id)
  message.success('Scenario removed')
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
    <div
      class="scenario-drop-surface"
      :class="{ 'is-drag-active': isDragActive }"
      @dragenter="onDragEnter"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
    >
      <div class="scenario-browser-toolbar">
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
    <n-spin :show="scenarioStore.isInstalledLoading">
      <div v-if="scenarioStore.installedScenarios.length" class="scenario-grid">
        <button
          v-for="scenario in scenarioStore.installedScenarios"
          :key="scenario.id"
          class="scenario-card"
          :class="{ 'is-disabled': !scenario.enabled }"
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
              <div class="scenario-card-meta">
                <n-tag size="small" :bordered="false">
                  {{ scenario.source === 'installed' ? 'Installed' : 'Bundled' }}
                </n-tag>
                <span class="scenario-version">v{{ scenario.version }}</span>
              </div>
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
            <div class="scenario-actions" @click.stop>
              <n-button size="small" @click="toggleScenario(scenario)">
                {{ scenario.enabled ? 'Disable' : 'Enable' }}
              </n-button>
              <n-button
                v-if="scenario.source === 'installed'"
                size="small"
                type="error"
                @click="removeScenario(scenario)"
              >
                Remove
              </n-button>
            </div>
          </div>
        </button>
      </div>
      <n-empty v-else description="未发现可用 scenario" />
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
  justify-content: flex-end;
  margin-bottom: 12px;
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
