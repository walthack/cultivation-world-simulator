import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { scenarioApi } from '@/api/modules/scenario'
import type {
  ScenarioDraftDTO,
  ScenarioGenerateResultDTO,
  ScenarioSaveDraftResultDTO,
  ScenarioTemplateMetaDTO,
} from '@/types/api'

const STORAGE_KEY = 'cws.scenarioWizard.draft.v0.7'

export function createEmptyScenarioDraft(): ScenarioDraftDTO {
  return {
    scenario: {
      schema_version: '0.1',
      scenario_id: '',
      title: '',
      version: '1.0',
      author: '',
      description: '',
      tags: [],
      world_preset: {
        preset_id: 'default',
      },
      world_background: '',
      initial_state: {
        year: 1,
        month: 1,
        avatars: [],
        relationships: [],
        sects: [],
        world_flags: {},
      },
    },
    timeline: {
      schema_version: '0.1',
      events: [],
    },
  }
}

function cloneDraft(draft: ScenarioDraftDTO): ScenarioDraftDTO {
  return JSON.parse(JSON.stringify(draft)) as ScenarioDraftDTO
}

function normalizeDraft(value: unknown): ScenarioDraftDTO {
  const empty = createEmptyScenarioDraft()
  if (!value || typeof value !== 'object') return empty
  const draft = value as Partial<ScenarioDraftDTO>
  return {
    scenario: {
      ...empty.scenario,
      ...(draft.scenario || {}),
      world_preset: {
        ...empty.scenario.world_preset,
        ...(draft.scenario?.world_preset || {}),
      },
      initial_state: {
        ...empty.scenario.initial_state,
        ...(draft.scenario?.initial_state || {}),
        avatars: draft.scenario?.initial_state?.avatars || [],
        relationships: draft.scenario?.initial_state?.relationships || [],
        sects: draft.scenario?.initial_state?.sects || [],
      },
    },
    timeline: {
      ...empty.timeline,
      ...(draft.timeline || {}),
      events: draft.timeline?.events || [],
    },
  }
}

export const useScenarioWizardStore = defineStore('scenarioWizard', () => {
  const draft = ref<ScenarioDraftDTO>(createEmptyScenarioDraft())
  const templates = ref<ScenarioTemplateMetaDTO[]>([])
  const isLoadingTemplates = ref(false)
  const isGenerating = ref(false)
  const isSaving = ref(false)
  const lastGenerateResult = ref<ScenarioGenerateResultDTO | null>(null)
  const lastSaveResult = ref<ScenarioSaveDraftResultDTO | null>(null)

  const templateOptions = computed(() => templates.value.map((item) => ({
    label: item.title,
    value: item.category,
  })))

  function hydrateFromLocalStorage() {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    try {
      draft.value = normalizeDraft(JSON.parse(raw))
    } catch {
      draft.value = createEmptyScenarioDraft()
    }
  }

  function persistDraft() {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(draft.value))
  }

  watch(draft, persistDraft, { deep: true })

  function resetDraft() {
    draft.value = createEmptyScenarioDraft()
    lastGenerateResult.value = null
    lastSaveResult.value = null
    persistDraft()
  }

  function replaceDraft(nextDraft: ScenarioDraftDTO) {
    draft.value = normalizeDraft(cloneDraft(nextDraft))
  }

  async function fetchTemplates() {
    isLoadingTemplates.value = true
    try {
      const data = await scenarioApi.fetchTemplates()
      templates.value = data.templates || []
    } finally {
      isLoadingTemplates.value = false
    }
  }

  async function applyTemplate(category: string) {
    const data = await scenarioApi.loadTemplate(category)
    replaceDraft(data)
  }

  async function generate(description: string, hints: Record<string, unknown>) {
    isGenerating.value = true
    try {
      const result = await scenarioApi.generateScenario(description, hints)
      lastGenerateResult.value = result
      if (result.ok && result.draft) {
        replaceDraft(result.draft)
      }
      return result
    } finally {
      isGenerating.value = false
    }
  }

  async function saveDraft() {
    isSaving.value = true
    try {
      const result = await scenarioApi.saveDraft(draft.value)
      lastSaveResult.value = result
      return result
    } finally {
      isSaving.value = false
    }
  }

  return {
    draft,
    templates,
    templateOptions,
    isLoadingTemplates,
    isGenerating,
    isSaving,
    lastGenerateResult,
    lastSaveResult,
    hydrateFromLocalStorage,
    resetDraft,
    replaceDraft,
    fetchTemplates,
    applyTemplate,
    generate,
    saveDraft,
  }
})

export { STORAGE_KEY as SCENARIO_WIZARD_STORAGE_KEY }
