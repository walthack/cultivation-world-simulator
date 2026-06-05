import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ScenarioBadge from '@/components/game/panels/ScenarioBadge.vue'

let mockStatus: any

vi.mock('@/stores/scenario', () => ({
  useScenarioStore: () => ({
    get status() {
      return mockStatus
    },
  }),
}))

describe('ScenarioBadge', () => {
  beforeEach(() => {
    mockStatus = {
      active: true,
      title: '六朝纪事',
    }
  })

  it('renders title when scenario is active', () => {
    const wrapper = mount(ScenarioBadge)

    expect(wrapper.text()).toContain('六朝纪事')
  })

  it('does not render when scenario is inactive', () => {
    mockStatus = { active: false }

    const wrapper = mount(ScenarioBadge)

    expect(wrapper.find('.scenario-badge').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('六朝纪事')
  })
})
