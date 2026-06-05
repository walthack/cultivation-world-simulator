import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GameStartPanel from '@/components/game/panels/system/GameStartPanel.vue'

const {
  startDrafts,
  fetchInstalledScenariosMock,
  newGameDraft,
  installedScenarios,
} = vi.hoisted(() => ({
  startDrafts: [] as any[],
  fetchInstalledScenariosMock: vi.fn(),
  installedScenarios: [] as any[],
  newGameDraft: {
    content_locale: 'zh-CN',
    init_npc_num: 9,
    sect_num: 3,
    npc_awakening_rate_per_month: 0.01,
    world_lore: '',
    scenario_id: null as string | null,
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('naive-ui', () => ({
  useMessage: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
  NForm: {
    name: 'NForm',
    template: '<form class="n-form"><slot /></form>',
    props: ['labelPlacement', 'labelWidth', 'requireMarkPlacement', 'disabled'],
  },
  NFormItem: {
    name: 'NFormItem',
    template: '<label class="n-form-item"><span>{{ label }}</span><slot /></label>',
    props: ['label', 'path'],
  },
  NInputNumber: {
    name: 'NInputNumber',
    template: '<input class="n-input-number" :value="value" />',
    props: ['value', 'min', 'max', 'step', 'format', 'parse'],
    emits: ['update:value'],
  },
  NInput: {
    name: 'NInput',
    template: '<textarea class="n-input" :value="value" />',
    props: ['value', 'type', 'placeholder', 'autosize', 'maxlength', 'showCount'],
    emits: ['update:value'],
  },
  NSelect: {
    name: 'NSelect',
    template: `
      <div class="n-select">
        <button
          v-for="option in options"
          :key="option.value"
          class="scenario-option"
          type="button"
          @click="$emit('update:value', option.value)"
        >
          {{ option.label }}
        </button>
      </div>
    `,
    props: ['value', 'options'],
    emits: ['update:value'],
  },
  NButton: {
    name: 'NButton',
    template: '<button class="n-button" type="button" @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['type', 'size', 'loading', 'text'],
    emits: ['click'],
  },
  NModal: {
    name: 'NModal',
    template: '<div v-if="show" class="n-modal"><slot /><slot name="footer" /></div>',
    props: ['show'],
    emits: ['update:show'],
  },
  NSpin: {
    name: 'NSpin',
    template: '<div><slot /></div>',
    props: ['show'],
  },
  NTag: {
    name: 'NTag',
    template: '<span><slot /></span>',
    props: ['size', 'bordered'],
  },
  NEmpty: {
    name: 'NEmpty',
    template: '<div>{{ description }}</div>',
    props: ['description'],
  },
}))

vi.mock('@/stores/setting', () => ({
  useSettingStore: () => ({
    newGameDraft,
    updateNewGameDraft: (patch: Record<string, unknown>) => {
      Object.assign(newGameDraft, patch)
    },
    startGameWithDraft: vi.fn(async () => {
      startDrafts.push({ ...newGameDraft })
      return { status: 'ok', message: 'started' }
    }),
  }),
}))

vi.mock('@/stores/scenario', () => ({
  useScenarioStore: () => ({
    installedScenarios,
    isInstalledLoading: false,
    fetchInstalledScenarios: fetchInstalledScenariosMock,
  }),
}))

describe('GameStartPanel scenario picker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    startDrafts.length = 0
    newGameDraft.scenario_id = null
    installedScenarios.length = 0
    installedScenarios.push(
      {
        id: 'liuchao',
        name: '六朝纪事',
        version: '1.0',
        author: 'Chaldeas',
        description: 'liuchao',
        tags: [],
        cover_image: null,
        source: 'bundled',
        enabled: true,
      },
      {
        id: 'sanguo',
        name: '三国仙纪',
        version: '1.0',
        author: 'Chaldeas',
        description: 'sanguo',
        tags: [],
        cover_image: null,
        source: 'installed',
        enabled: true,
      },
    )
  })

  it('scenario picker option list includes default and installed scenarios', () => {
    const wrapper = mount(GameStartPanel, {
      props: { readonly: false },
    })

    expect(fetchInstalledScenariosMock).toHaveBeenCalled()
    expect(wrapper.text()).toContain('默认游戏（无 scenario）')
    expect(wrapper.text()).toContain('六朝纪事 v1.0')
    expect(wrapper.text()).toContain('三国仙纪 v1.0')
  })

  it('hides disabled scenarios from picker', () => {
    installedScenarios[1].enabled = false

    const wrapper = mount(GameStartPanel, {
      props: { readonly: false },
    })

    expect(wrapper.text()).toContain('默认游戏（无 scenario）')
    expect(wrapper.text()).toContain('六朝纪事 v1.0')
    expect(wrapper.text()).not.toContain('三国仙纪 v1.0')
  })

  it('start payload includes scenario_id', async () => {
    const wrapper = mount(GameStartPanel, {
      props: { readonly: false },
    })

    await wrapper.findAll('.scenario-option')[2].trigger('click')
    await wrapper.findAll('.n-button').at(-1)!.trigger('click')

    expect(startDrafts[0]).toMatchObject({ scenario_id: 'sanguo' })
  })
})
