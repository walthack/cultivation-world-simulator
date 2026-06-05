<script setup lang="ts">
import { computed, ref } from 'vue'
import { NButton, NEmpty, NModal, NTag, useMessage } from 'naive-ui'

import { useScenarioStore } from '@/stores/scenario'
import type { CompatResult, RepositoryScenarioDTO, RepositoryUpdateDTO } from '@/types/api'

const props = defineProps<{
  activeTab: 'installed' | 'downloaded' | 'updates'
}>()

const emit = defineEmits<{
  (event: 'select', scenario: RepositoryScenarioDTO): void
}>()

const scenarioStore = useScenarioStore()
const message = useMessage()
const pendingConfirm = ref<{
  kind: 'install' | 'update'
  title: string
  downloadId: string
  installedScenarioId?: string
  compatibility: CompatResult
} | null>(null)

const installed = computed(() => scenarioStore.repository.installed)
const downloaded = computed(() => scenarioStore.repository.downloaded)
const updates = computed(() => scenarioStore.repository.updates)

function verificationLabel(scenario: RepositoryScenarioDTO): string {
  const status = scenario.verification?.status ?? 'unsigned'
  if (status === 'verified') return '✓ verified'
  if (status === 'modified') return '⚠ modified'
  return '○ unsigned'
}

function shortFingerprint(scenario: RepositoryScenarioDTO): string {
  const fingerprint = scenario.fingerprint || scenario.verification?.computed || ''
  return fingerprint.startsWith('sha256:') ? fingerprint.slice('sha256:'.length, 'sha256:'.length + 8) : 'unsigned'
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

async function exportScenario(scenario: RepositoryScenarioDTO) {
  const result = await scenarioStore.exportScenario(scenario.id)
  downloadBlob(result.blob, result.filename)
}

async function installScenario(scenario: RepositoryScenarioDTO, confirmWarnings = false) {
  if (!scenario.download_id) return
  const result = await scenarioStore.installFromDownload(scenario.download_id, confirmWarnings)
  if (result.status === 'warning' && !confirmWarnings) {
    pendingConfirm.value = {
      kind: 'install',
      title: scenario.name,
      downloadId: scenario.download_id,
      compatibility: result.compatibility,
    }
    return
  }
  message.success('Scenario installed')
}

async function updateScenario(update: RepositoryUpdateDTO, confirmWarnings = false) {
  const downloadId = update.downloaded.download_id
  if (!downloadId) return
  const result = await scenarioStore.updateFromDownload(update.installed.id, downloadId, confirmWarnings)
  if (result.status === 'warning' && !confirmWarnings) {
    pendingConfirm.value = {
      kind: 'update',
      title: update.downloaded.name,
      installedScenarioId: update.installed.id,
      downloadId,
      compatibility: result.compatibility,
    }
    return
  }
  message.success('Scenario updated')
}

async function confirmCompatWarning() {
  const pending = pendingConfirm.value
  if (!pending) return
  pendingConfirm.value = null
  if (pending.kind === 'install') {
    await installScenario({ id: '', download_id: pending.downloadId, name: pending.title } as RepositoryScenarioDTO, true)
  } else if (pending.installedScenarioId) {
    await scenarioStore.updateFromDownload(pending.installedScenarioId, pending.downloadId, true)
    message.success('Scenario updated')
  }
}

function cancelCompatWarning() {
  pendingConfirm.value = null
}
</script>

<template>
  <div class="scenario-repository-tabs">
    <div v-if="activeTab === 'installed'" class="scenario-grid">
      <button
        v-for="scenario in installed"
        :key="scenario.id"
        class="scenario-card"
        :class="{ 'is-disabled': !scenario.enabled }"
        type="button"
        @click="emit('select', scenario)"
      >
        <div class="scenario-card-body">
          <div class="scenario-card-header">
            <h4>{{ scenario.name }}</h4>
            <span class="scenario-version">v{{ scenario.version }}</span>
          </div>
          <div class="scenario-card-meta">
            <n-tag size="small" :bordered="false">{{ scenario.source }}</n-tag>
            <n-tag size="small" :bordered="false">{{ verificationLabel(scenario) }}</n-tag>
            <span class="scenario-fingerprint">{{ shortFingerprint(scenario) }}</span>
          </div>
          <div v-if="scenario.author" class="scenario-author">{{ scenario.author }}</div>
          <p>{{ scenario.description }}</p>
          <div class="scenario-actions" @click.stop>
            <n-button size="small" @click="exportScenario(scenario)">Export</n-button>
          </div>
        </div>
      </button>
      <n-empty v-if="!installed.length" description="No installed scenarios" />
    </div>

    <div v-else-if="activeTab === 'downloaded'" class="scenario-grid">
      <article v-for="scenario in downloaded" :key="scenario.download_id || scenario.id" class="scenario-card">
        <div class="scenario-card-body">
          <div class="scenario-card-header">
            <h4>{{ scenario.name }}</h4>
            <span class="scenario-version">v{{ scenario.version }}</span>
          </div>
          <div class="scenario-card-meta">
            <n-tag size="small" :bordered="false">{{ verificationLabel(scenario) }}</n-tag>
            <span class="scenario-fingerprint">{{ shortFingerprint(scenario) }}</span>
          </div>
          <p>{{ scenario.description }}</p>
          <div class="scenario-actions">
            <n-button size="small" type="primary" @click="installScenario(scenario)">Install</n-button>
          </div>
        </div>
      </article>
      <n-empty v-if="!downloaded.length" description="No downloaded scenarios" />
    </div>

    <div v-else class="scenario-grid">
      <article v-for="update in updates" :key="`${update.installed.id}:${update.downloaded.version}`" class="scenario-card">
        <div class="scenario-card-body">
          <div class="scenario-card-header">
            <h4>{{ update.downloaded.name }}</h4>
            <span class="scenario-version">v{{ update.installed.version }} → v{{ update.downloaded.version }}</span>
          </div>
          <div class="scenario-card-meta">
            <n-tag size="small" :bordered="false">{{ verificationLabel(update.downloaded) }}</n-tag>
            <span class="scenario-fingerprint">{{ shortFingerprint(update.downloaded) }}</span>
          </div>
          <p>{{ update.downloaded.description }}</p>
          <div class="scenario-actions">
            <n-button size="small" type="primary" @click="updateScenario(update)">Update</n-button>
          </div>
        </div>
      </article>
      <n-empty v-if="!updates.length" description="No updates available" />
    </div>
  </div>

  <n-modal :show="pendingConfirm !== null" preset="card" title="Compatibility warning" class="scenario-compat-modal">
    <p v-for="warning in pendingConfirm?.compatibility.warnings || []" :key="warning">{{ warning }}</p>
    <template #footer>
      <div class="scenario-browser-footer">
        <n-button size="small" @click="cancelCompatWarning">Cancel</n-button>
        <n-button size="small" type="primary" @click="confirmCompatWarning">Continue</n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.scenario-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
}

.scenario-card {
  display: flex;
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

.scenario-card-body {
  min-width: 0;
  flex: 1;
}

.scenario-card-header,
.scenario-card-meta,
.scenario-actions,
.scenario-browser-footer {
  display: flex;
  align-items: center;
  gap: 8px;
}

.scenario-card-header {
  justify-content: space-between;
}

.scenario-card h4 {
  margin: 0;
  color: #f0cf86;
  font-size: 1rem;
  line-height: 1.25;
}

.scenario-version,
.scenario-author,
.scenario-fingerprint,
.scenario-card p {
  color: #aaa;
  font-size: 0.85rem;
}

.scenario-card p {
  margin: 8px 0;
  line-height: 1.45;
}

.scenario-actions {
  flex-wrap: wrap;
  margin-top: 10px;
}

.scenario-browser-footer {
  justify-content: flex-end;
}

.scenario-compat-modal {
  width: min(440px, calc(100vw - 32px));
}
</style>
