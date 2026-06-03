import { ref } from 'vue'

export function useScenarioBrowserModal() {
  const showScenarioBrowser = ref(false)
  const selectedScenarioId = ref<string | null>(null)

  function openScenarioBrowser() {
    showScenarioBrowser.value = true
  }

  function closeScenarioBrowser() {
    showScenarioBrowser.value = false
  }

  function selectScenario(scenarioId: string) {
    selectedScenarioId.value = scenarioId
    closeScenarioBrowser()
  }

  return {
    showScenarioBrowser,
    selectedScenarioId,
    openScenarioBrowser,
    closeScenarioBrowser,
    selectScenario,
  }
}
