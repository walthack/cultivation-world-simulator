import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import ScenarioBadge from '@/components/game/panels/ScenarioBadge.vue'
import ScenarioOverviewModal from '@/components/game/panels/ScenarioOverviewModal.vue'

let mockStatus: any
const refreshStatusMock = vi.fn()

vi.mock('naive-ui', () => ({
  NModal: {
    name: 'NModal',
    template: '<div v-if="show" class="n-modal"><slot /></div>',
    props: ['show', 'title', 'preset'],
    emits: ['update:show'],
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
    isLoaded: true,
    refreshStatus: refreshStatusMock,
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
    vi.clearAllMocks()
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
})
