import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import ModManagerModal from '@/components/game/panels/system/ModManagerModal.vue'
import SettingsPanel from '@/components/settings/SettingsPanel.vue'
import { useSettingStore } from '@/stores/setting'
import { createTestI18n, testDefaultLocale } from '@/__tests__/utils/i18n'

const mod = {
  mod_id: 'sample',
  name: 'Sample Mod',
  version: '1.0.0',
  author: 'Tester',
  description: 'A sample mod',
  fingerprint: 'sha256:abc',
  dependencies: [],
  extensions: {
    rules: { predicates: ['sample_predicate'], effects: [] },
    assets: { portraits: ['p.png'], localizations: { 'en-US': 'locale/en_US.json' } },
    llm: { prompts: [{ key: 'npc_action' }] },
    code: { hooks: ['on_world_init'] },
  },
  path: '/mods/sample',
  enabled: true,
  python_hooks_enabled: false,
  python_hooks_declared: true,
}

async function settle() {
  for (let i = 0; i < 5; i += 1) {
    await Promise.resolve()
    await nextTick()
  }
}

function jsonResponse(data: unknown) {
  return Promise.resolve(new Response(JSON.stringify({ ok: true, data }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  }))
}

function mockFetch(overrides: Record<string, unknown> = {}) {
  const defaultData: Record<string, unknown> = {
    '/api/v1/query/mods/installed': { mods: [mod], conflicts: [] },
    '/api/v1/query/mods/load-order': { load_order: ['sample'] },
    '/api/v1/query/mods/extensions-active': {
      extensions: [
      {
        kind: 'predicate',
        name: 'sample_predicate',
        mod_id: 'sample',
        python_required: true,
        category: 'python',
        active: false,
        inert: true,
      },
      {
        kind: 'llm_prompt',
        name: 'npc_action',
        mod_id: 'sample',
        python_required: false,
        category: 'data-only',
        active: true,
        inert: false,
      },
    ],
    },
    '/api/v1/command/mod/set-enabled': mod,
    '/api/v1/command/mod/reorder': { load_order: ['sample'] },
    '/api/v1/command/mod/uninstall': { mod_id: 'sample' },
    '/api/settings': {
      schema_version: 2,
      advanced_runtime_control: false,
      allow_trusted_python_mods: true,
      ui: { locale: 'en-US', audio: { bgm_volume: 0.5, sfx_volume: 0.5 } },
      simulation: { auto_save_enabled: false, max_auto_saves: 5 },
      llm: { profile: { base_url: '', model_name: '', fast_model_name: '', mode: 'default', max_concurrent_requests: 10, has_api_key: false, api_format: 'openai' } },
      new_game_defaults: { content_locale: 'en-US', init_npc_num: 9, sect_num: 3, npc_awakening_rate_per_month: 0.01, world_lore: '' },
    },
  }
  const data = { ...defaultData, ...overrides }
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    const path = url.startsWith('http') ? new URL(url).pathname : url
    return jsonResponse(data[path])
  }))
}

describe('ModManagerModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.unstubAllGlobals()
    mockFetch()
  })

  it('renders mod list with Python badge', async () => {
    const wrapper = mount(ModManagerModal)
    await settle()
    expect(wrapper.text()).toContain('Sample Mod')
    expect(wrapper.text()).toContain('Python hooks: disabled')
  })

  it('enable and disable toggle works', async () => {
    const wrapper = mount(ModManagerModal)
    await settle()
    const checkbox = wrapper.find('input[type="checkbox"]')
    await checkbox.setValue(false)
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/v1/command/mod/set-enabled'), expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ mod_id: 'sample', enabled: false }),
    }))
  })

  it('reorders load order via drag', async () => {
    mockFetch({
      '/api/v1/query/mods/installed': { mods: [{ ...mod, mod_id: 'a', name: 'A' }, { ...mod, mod_id: 'b', name: 'B' }], conflicts: [] },
      '/api/v1/query/mods/load-order': { load_order: ['a', 'b'] },
    })
    const wrapper = mount(ModManagerModal)
    await settle()
    await wrapper.findAll('.tab-row button')[2].trigger('click')
    const rows = wrapper.findAll('.order-row')
    await rows[1].trigger('dragstart')
    await rows[0].trigger('drop')
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/v1/command/mod/reorder'), expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ mod_ids: ['b', 'a'] }),
    }))
  })

  it('shows conflict modal on install or refresh conflicts', async () => {
    mockFetch({
      '/api/v1/query/mods/installed': {
        mods: [mod],
        conflicts: [{ kind: 'predicate', name: 'same_predicate', mod_ids: ['a', 'b'] }],
      },
    })
    const wrapper = mount(ModManagerModal)
    await settle()
    expect(wrapper.find('.conflict-modal').exists()).toBe(true)
    expect(wrapper.text()).toContain('same_predicate')
  })

  it('extension inspection view shows data-only vs Python categorization', async () => {
    const wrapper = mount(ModManagerModal)
    await settle()
    await wrapper.findAll('.tab-row button')[3].trigger('click')
    expect(wrapper.text()).toContain('Python')
    expect(wrapper.text()).toContain('data-only')
  })
})

describe('SettingsPanel Python trust gate', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.unstubAllGlobals()
    mockFetch()
  })

  it('shows trust warning modal before allow_trusted_python_mods toggle', async () => {
    const i18n = createTestI18n({
      ui: {
        settings: 'Settings',
        language: 'Language',
        language_accessible_label: 'Language',
        sound: 'Sound',
        bgm_volume: 'Music',
        sfx_volume: 'Sound FX',
        auto_save: 'Auto Save',
        auto_save_desc: 'Auto save',
      },
    }, testDefaultLocale)
    const wrapper = mount(SettingsPanel, {
      global: {
        plugins: [i18n],
        stubs: {
          NSelect: true,
          NSlider: true,
          NSwitch: {
            props: ['value'],
            emits: ['update:value'],
            template: '<button class="switch" @click="$emit(\'update:value\', true)">switch</button>',
          },
          'n-select': true,
          'n-slider': true,
          'n-switch': {
            props: ['value'],
            emits: ['update:value'],
            template: '<button class="switch" @click="$emit(\'update:value\', true)">switch</button>',
          },
        },
      },
    })
    useSettingStore().allowTrustedPythonMods = false
    await wrapper.findComponent('[data-testid="python-mod-switch"]').vm.$emit('update:value', true)
    await nextTick()
    expect(wrapper.text()).toContain('You are about to enable Python mod execution. Untrusted mods can do anything the game can do. Continue?')
    await wrapper.find('.trust-actions .danger').trigger('click')
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/api/settings'), expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ allow_trusted_python_mods: true }),
    }))
  })
})
