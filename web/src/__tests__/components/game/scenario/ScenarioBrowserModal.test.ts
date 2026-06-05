import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ScenarioBrowserModal from '@/components/game/panels/system/ScenarioBrowserModal.vue'
import ScenarioRepositoryTabs from '@/components/game/panels/system/ScenarioRepositoryTabs.vue'

const scenarioState = vi.hoisted(() => ({
  fetchRepositoryMock: vi.fn(),
  exportScenarioMock: vi.fn(),
  installFromDownloadMock: vi.fn(),
  updateFromDownloadMock: vi.fn(),
  importScenarioFileMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
  infoMock: vi.fn(),
  repository: { installed: [] as any[], downloaded: [] as any[], updates: [] as any[] },
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
    get repository() {
      return scenarioState.repository
    },
    isRepositoryLoading: false,
    fetchRepository: scenarioState.fetchRepositoryMock,
    exportScenario: scenarioState.exportScenarioMock,
    installFromDownload: scenarioState.installFromDownloadMock,
    updateFromDownload: scenarioState.updateFromDownloadMock,
    importScenarioFile: scenarioState.importScenarioFileMock,
  }),
}))

describe('ScenarioBrowserModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    scenarioState.repository = {
      installed: [
      {
        id: 'liuchao',
        download_id: null,
        name: '六朝纪事',
        version: '1.0',
        author: 'Chaldeas',
        description: 'Stage 1 minimal 六朝 scenario demo.',
        tags: ['历史', '六朝'],
        cover_image: null,
        source: 'bundled',
        enabled: true,
        fingerprint: 'sha256:1234567890abcdef',
        verification: { status: 'verified', computed: 'sha256:1234567890abcdef', claimed: 'sha256:1234567890abcdef' },
      },
      {
        id: 'sanguo',
        download_id: null,
        name: '三国仙纪',
        version: '1.0',
        author: 'Chaldeas',
        description: 'Stage 2d minimal 三国 scenario demo.',
        tags: [],
        cover_image: null,
        source: 'installed',
        enabled: false,
        fingerprint: 'sha256:abcdef1234567890',
        verification: { status: 'unsigned', computed: 'sha256:abcdef1234567890', claimed: null },
      },
      ],
      downloaded: [
        {
          id: 'xianxia',
          download_id: 'xianxia',
          name: 'Xianxia Download',
          version: '1.1',
          author: null,
          description: 'Downloaded package.',
          tags: [],
          cover_image: null,
          source: 'downloaded',
          enabled: true,
          fingerprint: 'sha256:ffeeddcc00112233',
          verification: { status: 'modified', computed: 'sha256:00112233ffeeddcc', claimed: 'sha256:ffeeddcc00112233' },
        },
      ],
      updates: [
        {
          installed: {
            id: 'liuchao',
            download_id: null,
            name: '六朝纪事',
            version: '1.0',
            author: 'Chaldeas',
            description: '',
            tags: [],
            cover_image: null,
            source: 'installed',
            enabled: true,
            fingerprint: 'sha256:1234567890abcdef',
            verification: { status: 'verified', computed: 'sha256:1234567890abcdef', claimed: 'sha256:1234567890abcdef' },
          },
          downloaded: {
            id: 'liuchao',
            download_id: 'liuchao',
            name: '六朝纪事',
            version: '1.2',
            author: 'Chaldeas',
            description: 'Update package.',
            tags: [],
            cover_image: null,
            source: 'downloaded',
            enabled: true,
            fingerprint: 'sha256:9999999900000000',
            verification: { status: 'verified', computed: 'sha256:9999999900000000', claimed: 'sha256:9999999900000000' },
          },
        },
      ],
    }
    scenarioState.exportScenarioMock.mockResolvedValue({ blob: new Blob(['zip']), filename: 'liuchao.zip' })
    scenarioState.installFromDownloadMock.mockResolvedValue({
      status: 'installed',
      moved: true,
      scenario_id: 'xianxia',
      compatibility: { status: 'pass', warnings: [], errors: [] },
    })
    scenarioState.updateFromDownloadMock.mockResolvedValue({
      status: 'updated',
      moved: true,
      scenario_id: 'liuchao',
      compatibility: { status: 'pass', warnings: [], errors: [] },
    })
  })

  it('renders installed scenarios from repository store', () => {
    const wrapper = mount(ScenarioBrowserModal, {
      props: { show: true },
    })

    expect(scenarioState.fetchRepositoryMock).toHaveBeenCalled()
    expect(wrapper.text()).toContain('六朝纪事')
    expect(wrapper.text()).toContain('三国仙纪')
    expect(wrapper.text()).toContain('Chaldeas')
    expect(wrapper.text()).toContain('12345678')
  })

  it('renders import button and drag-drop surface', () => {
    const wrapper = mount(ScenarioBrowserModal, {
      props: { show: true },
    })

    expect(wrapper.text()).toContain('Import...')
    expect(wrapper.find('.scenario-drop-surface').exists()).toBe(true)
    expect(wrapper.find('input[type="file"]').attributes('accept')).toBe('.zip')
  })

  it('switches tab navigation in ScenarioBrowserModal', async () => {
    const wrapper = mount(ScenarioBrowserModal, {
      props: { show: true },
    })

    expect(wrapper.text()).toContain('六朝纪事')
    await wrapper.findAll('.scenario-tab')[1].trigger('click')
    expect(wrapper.text()).toContain('Xianxia Download')
    await wrapper.findAll('.scenario-tab')[2].trigger('click')
    expect(wrapper.text()).toContain('v1.0 → v1.2')
  })

  it('emits selection event', async () => {
    const wrapper = mount(ScenarioBrowserModal, {
      props: { show: true },
    })

    await wrapper.findAll('.scenario-card')[0].trigger('click')

    expect(wrapper.emitted('select')?.[0]).toEqual(['liuchao'])
    expect(wrapper.emitted('update:show')?.[0]).toEqual([false])
  })

  it('card shows fingerprint truncation and verification badges', () => {
    const wrapper = mount(ScenarioRepositoryTabs, {
      props: { activeTab: 'downloaded' },
    })

    expect(wrapper.text()).toContain('ffeeddcc')
    expect(wrapper.text()).toContain('⚠ modified')
  })

  it('installed card shows unsigned badge when fingerprint is absent', () => {
    const wrapper = mount(ScenarioRepositoryTabs, {
      props: { activeTab: 'installed' },
    })

    expect(wrapper.text()).toContain('○ unsigned')
    expect(wrapper.text()).toContain('abcdef12')
  })

  it('install button calls install-from-download action', async () => {
    const wrapper = mount(ScenarioRepositoryTabs, {
      props: { activeTab: 'downloaded' },
    })

    await wrapper.find('.n-button').trigger('click')

    expect(scenarioState.installFromDownloadMock).toHaveBeenCalledWith('xianxia', false)
  })

  it('update button calls update action with installed and downloaded ids', async () => {
    const wrapper = mount(ScenarioRepositoryTabs, {
      props: { activeTab: 'updates' },
    })

    await wrapper.find('.n-button').trigger('click')

    expect(scenarioState.updateFromDownloadMock).toHaveBeenCalledWith('liuchao', 'liuchao', false)
  })

  it('export button triggers zip download', async () => {
    Object.defineProperty(URL, 'createObjectURL', { value: vi.fn(), configurable: true })
    Object.defineProperty(URL, 'revokeObjectURL', { value: vi.fn(), configurable: true })
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:scenario')
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    const clickMock = vi.fn()
    const wrapper = mount(ScenarioRepositoryTabs, {
      props: { activeTab: 'installed' },
    })
    const createElement = vi.spyOn(document, 'createElement').mockReturnValue({ click: clickMock } as unknown as HTMLAnchorElement)

    await wrapper.find('.n-button').trigger('click')

    expect(scenarioState.exportScenarioMock).toHaveBeenCalledWith('liuchao')
    expect(clickMock).toHaveBeenCalled()
    createElement.mockRestore()
    createObjectURL.mockRestore()
    revokeObjectURL.mockRestore()
  })

  it('compat warning modal proceeds on confirm', async () => {
    scenarioState.installFromDownloadMock
      .mockResolvedValueOnce({
        status: 'warning',
        moved: false,
        scenario_id: 'xianxia',
        compatibility: { status: 'warn', warnings: ['Requires newer CWS'], errors: [] },
      })
      .mockResolvedValueOnce({
        status: 'installed',
        moved: true,
        scenario_id: 'xianxia',
        compatibility: { status: 'warn', warnings: ['Requires newer CWS'], errors: [] },
      })
    const wrapper = mount(ScenarioRepositoryTabs, {
      props: { activeTab: 'downloaded' },
    })

    await wrapper.find('.n-button').trigger('click')
    expect(wrapper.text()).toContain('Requires newer CWS')
    await wrapper.findAll('.n-button').at(-1)!.trigger('click')

    expect(scenarioState.installFromDownloadMock).toHaveBeenLastCalledWith('xianxia', true)
  })
})
