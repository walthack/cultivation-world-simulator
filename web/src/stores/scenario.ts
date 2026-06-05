import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import { scenarioApi } from '@/api/modules/scenario'
import type {
  ExportResult,
  ImportResult,
  InstalledScenarioMeta,
  RepositoryDTO,
  ScenarioActivateMode,
  ScenarioDebugSnapshotDTO,
  ScenarioStatusResponseDTO,
} from '@/types/api'
import { logWarn } from '@/utils/appError'

function createEmptyStatus(): ScenarioStatusResponseDTO {
  return { active: false }
}

function createEmptyDebugSnapshot(): ScenarioDebugSnapshotDTO {
  return { state: {}, triggered_events: [], dispatch_log: [] }
}

function createEmptyRepository(): RepositoryDTO {
  return { installed: [], downloaded: [], updates: [] }
}

function isDebugErrorPayload(value: unknown): value is { ok: false; error: string } {
  return Boolean(value && typeof value === 'object' && 'ok' in value && (value as { ok?: unknown }).ok === false)
}

export const useScenarioStore = defineStore('scenario', () => {
  const status = shallowRef<ScenarioStatusResponseDTO>(createEmptyStatus())
  const installedScenarios = ref<InstalledScenarioMeta[]>([])
  const repository = shallowRef<RepositoryDTO>(createEmptyRepository())
  const debugSnapshot = shallowRef<ScenarioDebugSnapshotDTO>(createEmptyDebugSnapshot())
  const isLoading = ref(false)
  const isLoaded = ref(false)
  const isInstalledLoading = ref(false)
  const isRepositoryLoading = ref(false)
  const isDebugLoading = ref(false)

  let refreshRequestId = 0

  const isActive = computed(() => status.value.active)
  const activeStatus = computed(() => (status.value.active ? status.value : null))

  async function refreshStatus() {
    const currentRequestId = ++refreshRequestId
    isLoading.value = true

    try {
      const data = await scenarioApi.fetchScenarioStatus()
      if (currentRequestId !== refreshRequestId) return
      status.value = data
      isLoaded.value = true
    } catch (error) {
      if (currentRequestId !== refreshRequestId) return
      logWarn('ScenarioStore refresh status', error)
      status.value = createEmptyStatus()
      isLoaded.value = false
    } finally {
      if (currentRequestId === refreshRequestId) {
        isLoading.value = false
      }
    }
  }

  async function fetchInstalledScenarios() {
    isInstalledLoading.value = true
    try {
      const data = await scenarioApi.fetchInstalledScenarios()
      installedScenarios.value = data.scenarios ?? []
    } catch (error) {
      logWarn('ScenarioStore fetch installed scenarios', error)
      installedScenarios.value = []
    } finally {
      isInstalledLoading.value = false
    }
  }

  async function fetchRepository() {
    isRepositoryLoading.value = true
    try {
      repository.value = await scenarioApi.fetchRepository()
      installedScenarios.value = repository.value.installed
    } catch (error) {
      logWarn('ScenarioStore fetch repository', error)
      repository.value = createEmptyRepository()
    } finally {
      isRepositoryLoading.value = false
    }
  }

  async function refreshDebugSnapshot() {
    isDebugLoading.value = true
    try {
      const data = await scenarioApi.fetchDebugSnapshot()
      if (isDebugErrorPayload(data)) {
        debugSnapshot.value = createEmptyDebugSnapshot()
        return
      }
      debugSnapshot.value = data
    } catch (error) {
      logWarn('ScenarioStore refresh debug snapshot', error)
      debugSnapshot.value = createEmptyDebugSnapshot()
    } finally {
      isDebugLoading.value = false
    }
  }

  async function activateScenario(scenarioId: string, mode: ScenarioActivateMode) {
    const result = await scenarioApi.activateScenario(scenarioId, mode)
    await refreshStatus()
    await refreshDebugSnapshot()
    return result
  }

  async function deactivateScenario() {
    const result = await scenarioApi.deactivateScenario()
    await refreshStatus()
    await refreshDebugSnapshot()
    return result
  }

  async function reloadScenario() {
    const result = await scenarioApi.reloadScenario()
    await refreshStatus()
    await refreshDebugSnapshot()
    return result
  }

  async function importScenarioFile(
    file: File,
    options: { force?: boolean; renameTo?: string } = {},
  ): Promise<ImportResult> {
    const result = await scenarioApi.importScenario(file, options.force === true, options.renameTo)
    await fetchInstalledScenarios()
    await fetchRepository()
    return result
  }

  async function exportScenario(scenarioId: string): Promise<ExportResult> {
    return scenarioApi.exportScenario(scenarioId)
  }

  async function installFromDownload(downloadId: string, confirmWarnings = false) {
    const result = await scenarioApi.installFromDownload(downloadId, confirmWarnings)
    if (result.moved) {
      await fetchRepository()
    }
    return result
  }

  async function updateFromDownload(installedScenarioId: string, downloadId: string, confirmWarnings = false) {
    const result = await scenarioApi.updateFromDownload(installedScenarioId, downloadId, confirmWarnings)
    if (result.moved) {
      await fetchRepository()
    }
    return result
  }

  async function removeScenario(scenarioId: string) {
    const result = await scenarioApi.removeScenario(scenarioId)
    await fetchInstalledScenarios()
    await fetchRepository()
    return result
  }

  async function setScenarioEnabled(scenarioId: string, enabled: boolean) {
    const result = await scenarioApi.setScenarioEnabled(scenarioId, enabled)
    await fetchInstalledScenarios()
    await fetchRepository()
    return result
  }

  function reset() {
    status.value = createEmptyStatus()
    debugSnapshot.value = createEmptyDebugSnapshot()
    installedScenarios.value = []
    repository.value = createEmptyRepository()
    isLoading.value = false
    isInstalledLoading.value = false
    isRepositoryLoading.value = false
    isDebugLoading.value = false
    isLoaded.value = false
  }

  return {
    status,
    installedScenarios,
    repository,
    debugSnapshot,
    isActive,
    activeStatus,
    isLoading,
    isInstalledLoading,
    isRepositoryLoading,
    isDebugLoading,
    isLoaded,
    refreshStatus,
    fetchInstalledScenarios,
    fetchRepository,
    refreshDebugSnapshot,
    activateScenario,
    deactivateScenario,
    reloadScenario,
    importScenarioFile,
    exportScenario,
    installFromDownload,
    updateFromDownload,
    removeScenario,
    setScenarioEnabled,
    reset,
  }
})
