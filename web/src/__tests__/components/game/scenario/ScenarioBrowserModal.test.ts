import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ScenarioBrowserModal from '@/components/game/panels/system/ScenarioBrowserModal.vue'

const scenarioState = vi.hoisted(() => ({
  fetchInstalledScenariosMock: vi.fn(),
  installedScenarios: [] as any[],
}))

vi.mock('naive-ui', () => ({
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
      },
      {
        id: 'sanguo',
        name: '三国仙纪',
        version: '1.0',
        author: 'Chaldeas',
        description: 'Stage 2d minimal 三国 scenario demo.',
        tags: [],
        cover_image: null,
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

  it('emits selection event', async () => {
    const wrapper = mount(ScenarioBrowserModal, {
      props: { show: true },
    })

    await wrapper.findAll('.scenario-card')[1].trigger('click')

    expect(wrapper.emitted('select')?.[0]).toEqual(['sanguo'])
    expect(wrapper.emitted('update:show')?.[0]).toEqual([false])
  })
})
