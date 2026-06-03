import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import { scenarioApi } from '@/api/modules/scenario'
import type { ScenarioStatusResponseDTO } from '@/types/api'
import { logWarn } from '@/utils/appError'

function createEmptyStatus(): ScenarioStatusResponseDTO {
  return { active: false }
}

export const useScenarioStore = defineStore('scenario', () => {
  const status = shallowRef<ScenarioStatusResponseDTO>(createEmptyStatus())
  const isLoading = ref(false)
  const isLoaded = ref(false)

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

  function reset() {
    status.value = createEmptyStatus()
    isLoading.value = false
    isLoaded.value = false
  }

  return {
    status,
    isActive,
    activeStatus,
    isLoading,
    isLoaded,
    refreshStatus,
    reset,
  }
})
