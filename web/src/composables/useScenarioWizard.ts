import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useScenarioWizardStore } from '@/stores/scenarioWizard'
import type { ScenarioSaveDraftResultDTO } from '@/types/api'

export const SCENARIO_WIZARD_STEPS = [
  'Basics',
  'World',
  'LLM Assisted',
  'Initial State',
  'Timeline',
  'Review',
] as const

function hasText(value: unknown): boolean {
  return typeof value === 'string' && value.trim().length > 0
}

function downloadBase64Zip(result: ScenarioSaveDraftResultDTO) {
  const binary = window.atob(result.zip_base64)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  const blob = new Blob([bytes], { type: result.zip_mime || 'application/zip' })
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = result.zip_filename || `${result.scenario_id}.zip`
  anchor.click()
  window.URL.revokeObjectURL(url)
}

export function useScenarioWizard() {
  const store = useScenarioWizardStore()
  const { draft, templates, templateOptions, isGenerating, isSaving, lastGenerateResult } = storeToRefs(store)
  const currentStep = ref(0)
  const validationMessage = ref('')

  const stepName = computed(() => SCENARIO_WIZARD_STEPS[currentStep.value])
  const canGoBack = computed(() => currentStep.value > 0)
  const isLastStep = computed(() => currentStep.value === SCENARIO_WIZARD_STEPS.length - 1)

  function validateStep(step = currentStep.value): boolean {
    validationMessage.value = ''
    const scenario = draft.value.scenario
    if (step === 0) {
      if (!hasText(scenario.scenario_id)) validationMessage.value = 'Scenario id is required'
      else if (!hasText(scenario.title)) validationMessage.value = 'Title is required'
      else if (!hasText(scenario.version)) validationMessage.value = 'Version is required'
      else if (!hasText(scenario.description)) validationMessage.value = 'Description is required'
    } else if (step === 1) {
      if (!hasText(scenario.world_preset.preset_id)) validationMessage.value = 'World preset is required'
    } else if (step === 3) {
      if (!scenario.initial_state.avatars.length) validationMessage.value = 'At least one avatar is required'
    } else if (step === 4) {
      if (!draft.value.timeline.events.length) validationMessage.value = 'At least one timeline event is required'
    }
    return validationMessage.value.length === 0
  }

  function next() {
    if (!validateStep()) return false
    if (!isLastStep.value) currentStep.value += 1
    return true
  }

  function back() {
    if (currentStep.value > 0) currentStep.value -= 1
  }

  function goToStep(step: number) {
    if (step < 0 || step >= SCENARIO_WIZARD_STEPS.length) return
    currentStep.value = step
  }

  async function saveAndActivate() {
    if (!validateStep(0) || !validateStep(1) || !validateStep(3) || !validateStep(4)) {
      return null
    }
    return store.saveDraft()
  }

  async function exportZip() {
    const result = await saveAndActivate()
    if (result) downloadBase64Zip(result)
    return result
  }

  return {
    draft,
    templates,
    templateOptions,
    currentStep,
    stepName,
    steps: SCENARIO_WIZARD_STEPS,
    canGoBack,
    isLastStep,
    validationMessage,
    isGenerating,
    isSaving,
    lastGenerateResult,
    hydrateFromLocalStorage: store.hydrateFromLocalStorage,
    resetDraft: store.resetDraft,
    fetchTemplates: store.fetchTemplates,
    applyTemplate: store.applyTemplate,
    generate: store.generate,
    saveAndActivate,
    exportZip,
    validateStep,
    next,
    back,
    goToStep,
  }
}
