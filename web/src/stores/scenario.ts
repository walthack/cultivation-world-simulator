import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import { scenarioApi } from '@/api/modules/scenario'
import type { ImportResult, InstalledScenarioMeta, ScenarioStatusResponseDTO } from '@/types/api'
import { logWarn } from '@/utils/appError'

function createEmptyStatus(): ScenarioStatusResponseDTO {
  return { active: false }
}

export const useScenarioStore = defineStore('scenario', () => {
  const status = shallowRef<ScenarioStatusResponseDTO>(createEmptyStatus())
  const installedScenarios = ref<InstalledScenarioMeta[]>([])
  const isLoading = ref(false)
  const isLoaded = ref(false)
  const isInstalledLoading = ref(false)

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

  async function importScenarioFile(
    file: File,
    options: { force?: boolean; renameTo?: string } = {},
  ): Promise<ImportResult> {
    const result = await scenarioApi.importScenario(file, options.force === true, options.renameTo)
    await fetchInstalledScenarios()
    return result
  }

  async function removeScenario(scenarioId: string) {
    const result = await scenarioApi.removeScenario(scenarioId)
    await fetchInstalledScenarios()
    return result
  }

  async function setScenarioEnabled(scenarioId: string, enabled: boolean) {
    const result = await scenarioApi.setScenarioEnabled(scenarioId, enabled)
    await fetchInstalledScenarios()
    return result
  }

  function reset() {
    status.value = createEmptyStatus()
    installedScenarios.value = []
    isLoading.value = false
    isInstalledLoading.value = false
    isLoaded.value = false
  }

  return {
    status,
    installedScenarios,
    isActive,
    activeStatus,
    isLoading,
    isInstalledLoading,
    isLoaded,
    refreshStatus,
    fetchInstalledScenarios,
    importScenarioFile,
    removeScenario,
    setScenarioEnabled,
    reset,
  }
})
