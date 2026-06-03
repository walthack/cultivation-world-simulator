import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ScenarioWizardModal from '@/components/game/panels/system/ScenarioWizardModal.vue'
import { SCENARIO_WIZARD_STORAGE_KEY, useScenarioWizardStore } from '@/stores/scenarioWizard'

const apiState = vi.hoisted(() => ({
  fetchTemplates: vi.fn(),
  loadTemplate: vi.fn(),
  generateScenario: vi.fn(),
  saveDraft: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock('naive-ui', () => ({
  useMessage: () => ({
    success: apiState.success,
    error: apiState.error,
  }),
  NModal: {
    name: 'NModal',
    template: '<div v-if="show" class="n-modal"><slot /><slot name="footer" /></div>',
    props: ['show', 'preset', 'title'],
    emits: ['update:show'],
  },
  NButton: {
    name: 'NButton',
    template: '<button class="n-button" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['size', 'type', 'loading', 'disabled'],
    emits: ['click'],
  },
}))

vi.mock('@/api/modules/scenario', () => ({
  scenarioApi: {
    fetchTemplates: apiState.fetchTemplates,
    loadTemplate: apiState.loadTemplate,
    generateScenario: apiState.generateScenario,
    saveDraft: apiState.saveDraft,
  },
}))

function templateDraft() {
  return {
    scenario: {
      schema_version: '0.1',
      scenario_id: 'historical_starter',
      title: 'Three Courts Starter',
      version: '1.0',
      author: 'CWS Creator Toolkit',
      description: 'Historical starter.',
      tags: ['historical'],
      world_preset: { preset_id: 'liuchao' },
      initial_state: {
        year: 12,
        month: 1,
        avatars: [{ id: 'xiao-yan', realm: 'YUAN_YING', persona_traits: ['谋略'] }],
        relationships: [],
        sects: [],
        world_flags: {},
      },
    },
    timeline: {
      schema_version: '0.1',
      events: [
        {
          id: 'court-opening',
          type: 'main',
          trigger: { year: 12, month: 1 },
          name: 'Court Banners Raised',
          description: 'Opening.',
          effects: [{ type: 'set_flag', flag: 'court_banners_raised' }],
        },
      ],
    },
  }
}

const memoryStorage = (() => {
  let data: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => data[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      data[key] = String(value)
    }),
    removeItem: vi.fn((key: string) => {
      delete data[key]
    }),
    clear: vi.fn(() => {
      data = {}
    }),
  }
})()

describe('ScenarioWizardModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(window, 'localStorage', {
      value: memoryStorage,
      configurable: true,
    })
    memoryStorage.clear()
    setActivePinia(createPinia())
    apiState.fetchTemplates.mockResolvedValue({
      templates: [
        {
          category: 'historical',
          summary: 'Historical starter',
          title: 'Three Courts Starter',
          scenario_id: 'historical_starter',
          preset_id: 'liuchao',
        },
      ],
    })
    apiState.loadTemplate.mockResolvedValue(templateDraft())
    apiState.saveDraft.mockResolvedValue({
      status: 'saved',
      scenario_id: 'historical_starter',
      path: '/tmp/scenarios/historical_starter',
      warnings: [],
      zip_filename: 'historical_starter.zip',
      zip_mime: 'application/zip',
      zip_base64: 'UEs=',
    })
  })

  it('renders all 6 steps', () => {
    const wrapper = mount(ScenarioWizardModal, {
      props: { show: true },
    })

    expect(wrapper.text()).toContain('Basics')
    expect(wrapper.text()).toContain('World')
    expect(wrapper.text()).toContain('LLM Assisted')
    expect(wrapper.text()).toContain('Initial State')
    expect(wrapper.text()).toContain('Timeline')
    expect(wrapper.text()).toContain('Review')
  })

  it('prevents Next on missing required field', async () => {
    const wrapper = mount(ScenarioWizardModal, {
      props: { show: true },
    })

    await wrapper.findAll('.n-button').find((button) => button.text() === 'Next')?.trigger('click')

    expect(wrapper.text()).toContain('Scenario id is required')
  })

  it('template selection populates wizard fields', async () => {
    const wrapper = mount(ScenarioWizardModal, {
      props: { show: true },
    })
    await Promise.resolve()
    await wrapper.find('select').setValue('historical')
    await wrapper.findAll('.n-button').find((button) => button.text() === 'Load')?.trigger('click')
    await Promise.resolve()

    expect(apiState.loadTemplate).toHaveBeenCalledWith('historical')
    expect((wrapper.find('input[placeholder="my_scenario"]').element as HTMLInputElement).value)
      .toBe('historical_starter')
    expect(wrapper.text()).toContain('Three Courts Starter')
  })

  it('localStorage round-trips draft', async () => {
    const store = useScenarioWizardStore()
    store.replaceDraft(templateDraft())
    await Promise.resolve()

    setActivePinia(createPinia())
    const hydrated = useScenarioWizardStore()
    hydrated.hydrateFromLocalStorage()

    expect(window.localStorage.getItem(SCENARIO_WIZARD_STORAGE_KEY)).toContain('historical_starter')
    expect(hydrated.draft.scenario.scenario_id).toBe('historical_starter')
  })
})
