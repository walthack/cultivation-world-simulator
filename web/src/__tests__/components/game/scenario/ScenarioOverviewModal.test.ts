import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import ScenarioBadge from '@/components/game/panels/ScenarioBadge.vue'
import ScenarioOverviewModal from '@/components/game/panels/ScenarioOverviewModal.vue'

let mockStatus: any
let mockAdvancedRuntimeControl = false
let mockDebugSnapshot: any
const refreshStatusMock = vi.fn()
const fetchInstalledScenariosMock = vi.fn()
const refreshDebugSnapshotMock = vi.fn()
const activateScenarioMock = vi.fn()
const deactivateScenarioMock = vi.fn()
const reloadScenarioMock = vi.fn()

vi.mock('naive-ui', () => ({
  NModal: {
    name: 'NModal',
    template: '<div v-if="show" class="n-modal"><div v-if="title" class="n-modal-title">{{ title }}</div><slot /></div>',
    props: ['show', 'title', 'preset', 'positiveText', 'negativeText'],
    emits: ['update:show', 'positive-click', 'negative-click', 'close'],
  },
  NTag: {
    name: 'NTag',
    template: '<span class="n-tag"><slot /></span>',
    props: ['bordered', 'type', 'size'],
  },
  NSpin: {
    name: 'NSpin',
    template: '<div class="n-spin"><slot /></div>',
    props: ['show'],
  },
  NButton: {
    name: 'NButton',
    template: '<button class="n-button" @click="$emit(\'click\')"><slot /></button>',
    props: ['size', 'type', 'disabled'],
    emits: ['click'],
  },
  NSelect: {
    name: 'NSelect',
    template: '<select class="n-select"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>',
    props: ['value', 'options', 'placeholder'],
    emits: ['update:value'],
  },
  NTabs: {
    name: 'NTabs',
    template: '<div class="n-tabs"><slot /></div>',
    props: ['type', 'animated'],
  },
  NTabPane: {
    name: 'NTabPane',
    template: '<section class="n-tab-pane" :data-name="name"><div class="n-tab-label">{{ tab }}</div><slot /></section>',
    props: ['name', 'tab'],
  },
}))

vi.mock('@/stores/scenario', () => ({
  useScenarioStore: () => ({
    get status() {
      return mockStatus
    },
    get activeStatus() {
      return mockStatus.active ? mockStatus : null
    },
    isLoading: false,
    isDebugLoading: false,
    isLoaded: true,
    installedScenarios: [{ id: 'liuchao', name: '六朝纪事', enabled: true }],
    get debugSnapshot() {
      return mockDebugSnapshot
    },
    refreshStatus: refreshStatusMock,
    fetchInstalledScenarios: fetchInstalledScenariosMock,
    refreshDebugSnapshot: refreshDebugSnapshotMock,
    activateScenario: activateScenarioMock,
    deactivateScenario: deactivateScenarioMock,
    reloadScenario: reloadScenarioMock,
  }),
}))

vi.mock('@/stores/setting', () => ({
  useSettingStore: () => ({
    get advancedRuntimeControl() {
      return mockAdvancedRuntimeControl
    },
  }),
}))

function activeStatus() {
  return {
    active: true,
    scenario_id: 'liuchao',
    title: '六朝纪事',
    version: '1.0',
    world_background: '六朝并立，仙道隐现。',
    preset_id: 'liuchao',
    controlled_avatar: 'cheng-zongyang',
    world_flags: {},
    timeline: {
      total_events: 2,
      triggered_count: 1,
      events: [
        {
          id: 'liuchao-opening',
          name: '六朝开局',
          type: 'side_event',
          trigger: { year: 1, month: 1 },
          dynasty_id: null,
          at_region_id: null,
          triggered: true,
          triggered_month_stamp: '1-1',
        },
        {
          id: 'wang-zhe-passes-jiuyang',
          name: '王哲传程宗扬九阳',
          type: 'main',
          trigger: { year: 2, month: 3 },
          dynasty_id: 'song',
          at_region_id: 'linan',
          triggered: false,
        },
      ],
    },
  }
}

describe('ScenarioOverviewModal', () => {
  beforeEach(() => {
    mockStatus = activeStatus()
    mockAdvancedRuntimeControl = false
    mockDebugSnapshot = {
      state: { phase: 'opened', count: 2 },
      triggered_events: ['liuchao-opening'],
      dispatch_log: [
        { month_stamp: 'Y1M1', event_id: 'liuchao-opening', fired: true },
        { month_stamp: 'Y1M2', event_id: 'blocked-event', fired: false, reason: 'condition failed' },
      ],
    }
    vi.clearAllMocks()
    activateScenarioMock.mockResolvedValue({ ok: true })
    deactivateScenarioMock.mockResolvedValue({ ok: true })
    reloadScenarioMock.mockResolvedValue({ ok: true })
  })

  it('renders timeline events grouped by triggered and untriggered', () => {
    const wrapper = mount(ScenarioOverviewModal, {
      props: { show: true },
    })

    expect(wrapper.text()).toContain('已触发事件')
    expect(wrapper.text()).toContain('六朝开局')
    expect(wrapper.text()).toContain('已触发于 1-1')
    expect(wrapper.text()).toContain('未触发事件')
    expect(wrapper.text()).toContain('王哲传程宗扬九阳')
    expect(wrapper.text()).toContain('region: linan')
  })

  it('opens from badge click event', async () => {
    const Host = defineComponent({
      components: { ScenarioBadge, ScenarioOverviewModal },
      setup() {
        const show = ref(false)
        return () => h('div', [
          h(ScenarioBadge, { onOpen: () => { show.value = true } }),
          show.value ? h(ScenarioOverviewModal, {
            show: show.value,
            'onUpdate:show': (value: boolean) => { show.value = value },
          }) : null,
        ])
      },
    })
    const wrapper = mount(Host)

    await wrapper.find('.scenario-badge').trigger('click')
    await nextTick()

    expect(wrapper.find('.n-modal').exists()).toBe(true)
    expect(wrapper.text()).toContain('六朝纪事')
  })

  it('shows Debug tab only when advanced runtime control is enabled', async () => {
    const hidden = mount(ScenarioOverviewModal, {
      props: { show: true },
    })
    expect(hidden.text()).not.toContain('Debug')

    mockAdvancedRuntimeControl = true
    const visible = mount(ScenarioOverviewModal, {
      props: { show: true },
    })
    await nextTick()

    expect(visible.text()).toContain('Debug')
  })

  it('shows verbatim hot-swap warning in activate confirm modal', async () => {
    mockAdvancedRuntimeControl = true
    const wrapper = mount(ScenarioOverviewModal, {
      props: { show: true },
    })

    await wrapper.findAll('button').find((button) => button.text() === 'Activate hot-swap')?.trigger('click')
    await nextTick()

    expect(wrapper.text()).toContain('Activate scenario')
    expect(wrapper.text()).toContain('Hot-swap does not re-anchor time. Events scheduled before the current world time will not fire.')
  })

  it('opens deactivate confirm modal', async () => {
    mockAdvancedRuntimeControl = true
    const wrapper = mount(ScenarioOverviewModal, {
      props: { show: true },
    })

    await wrapper.findAll('button').find((button) => button.text() === 'Deactivate')?.trigger('click')
    await nextTick()

    expect(wrapper.text()).toContain('Deactivate scenario')
    expect(wrapper.text()).toContain('Existing avatars stay in the world')
  })

  it('renders debug state vars triggered events and dispatch log', () => {
    mockAdvancedRuntimeControl = true
    const wrapper = mount(ScenarioOverviewModal, {
      props: { show: true },
    })

    expect(wrapper.text()).toContain('State vars')
    expect(wrapper.text()).toContain('phase')
    expect(wrapper.text()).toContain('opened')
    expect(wrapper.text()).toContain('Triggered events')
    expect(wrapper.text()).toContain('liuchao-opening')
    expect(wrapper.text()).toContain('Dispatch log')
    expect(wrapper.text()).toContain('blocked-event')
    expect(wrapper.text()).toContain('condition failed')
  })
})
