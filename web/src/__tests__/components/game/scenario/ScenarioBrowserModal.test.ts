import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ScenarioBrowserModal from '@/components/game/panels/system/ScenarioBrowserModal.vue'

const scenarioState = vi.hoisted(() => ({
  fetchInstalledScenariosMock: vi.fn(),
  importScenarioFileMock: vi.fn(),
  removeScenarioMock: vi.fn(),
  setScenarioEnabledMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
  infoMock: vi.fn(),
  installedScenarios: [] as any[],
}))

vi.mock('naive-ui', () => ({
  useMessage: () => ({
    success: scenarioState.successMock,
    error: scenarioState.errorMock,
    info: scenarioState.infoMock,
  }),
  NModal: {
    name: 'NModal',
    template: '<div v-if="show" class="n-modal"><slot /><slot name="footer" /></div>',
    props: ['show', 'preset', 'title'],
    emits: ['update:show'],
  },
  NSpin: {
    name: 'NSpin',
    template: '<div class="n-spin"><slot /></div>',
    props: ['show'],
  },
  NTag: {
    name: 'NTag',
    template: '<span class="n-tag"><slot /></span>',
    props: ['size', 'bordered'],
  },
  NEmpty: {
    name: 'NEmpty',
    template: '<div class="n-empty">{{ description }}</div>',
    props: ['description'],
  },
  NButton: {
    name: 'NButton',
    template: '<button class="n-button" @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['size', 'type', 'loading'],
    emits: ['click'],
  },
}))

vi.mock('@/stores/scenario', () => ({
  useScenarioStore: () => ({
    get installedScenarios() {
      return scenarioState.installedScenarios
    },
    isInstalledLoading: false,
    fetchInstalledScenarios: scenarioState.fetchInstalledScenariosMock,
    importScenarioFile: scenarioState.importScenarioFileMock,
    removeScenario: scenarioState.removeScenarioMock,
    setScenarioEnabled: scenarioState.setScenarioEnabledMock,
  }),
}))

describe('ScenarioBrowserModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    scenarioState.installedScenarios = [
      {
        id: 'liuchao',
        name: '六朝纪事',
        version: '1.0',
        author: 'Chaldeas',
        description: 'Stage 1 minimal 六朝 scenario demo.',
        tags: ['历史', '六朝'],
        cover_image: null,
        source: 'bundled',
        enabled: true,
      },
      {
        id: 'sanguo',
        name: '三国仙纪',
        version: '1.0',
        author: 'Chaldeas',
        description: 'Stage 2d minimal 三国 scenario demo.',
        tags: [],
        cover_image: null,
        source: 'installed',
        enabled: false,
      },
    ]
  })

  it('renders installed scenarios from store', () => {
    const wrapper = mount(ScenarioBrowserModal, {
      props: { show: true },
    })

    expect(scenarioState.fetchInstalledScenariosMock).toHaveBeenCalled()
    expect(wrapper.text()).toContain('六朝纪事')
    expect(wrapper.text()).toContain('三国仙纪')
    expect(wrapper.text()).toContain('Chaldeas')
    expect(wrapper.text()).toContain('历史')
  })

  it('renders import button and drag-drop surface', () => {
    const wrapper = mount(ScenarioBrowserModal, {
      props: { show: true },
    })

    expect(wrapper.text()).toContain('Import...')
    expect(wrapper.find('.scenario-drop-surface').exists()).toBe(true)
    expect(wrapper.find('input[type="file"]').attributes('accept')).toBe('.zip')
  })

  it('shows source badges and manage controls per row', () => {
    const wrapper = mount(ScenarioBrowserModal, {
      props: { show: true },
    })

    expect(wrapper.text()).toContain('Bundled')
    expect(wrapper.text()).toContain('Installed')
    expect(wrapper.text()).toContain('Disable')
    expect(wrapper.text()).toContain('Enable')
    expect(wrapper.text()).toContain('Remove')
  })

  it('hides remove action for bundled scenarios', () => {
    const wrapper = mount(ScenarioBrowserModal, {
      props: { show: true },
    })

    const firstCard = wrapper.findAll('.scenario-card')[0]
    const secondCard = wrapper.findAll('.scenario-card')[1]
    expect(firstCard.text()).not.toContain('Remove')
    expect(secondCard.text()).toContain('Remove')
  })

  it('toggles disabled scenario without selecting it', async () => {
    const wrapper = mount(ScenarioBrowserModal, {
      props: { show: true },
    })

    const secondCard = wrapper.findAll('.scenario-card')[1]
    await secondCard.findAll('.n-button')[0].trigger('click')

    expect(scenarioState.setScenarioEnabledMock).toHaveBeenCalledWith('sanguo', true)
    expect(wrapper.emitted('select')).toBeUndefined()
  })

  it('emits selection event', async () => {
    const wrapper = mount(ScenarioBrowserModal, {
      props: { show: true },
    })

    await wrapper.findAll('.scenario-card')[0].trigger('click')

    expect(wrapper.emitted('select')?.[0]).toEqual(['liuchao'])
    expect(wrapper.emitted('update:show')?.[0]).toEqual([false])
  })
})
