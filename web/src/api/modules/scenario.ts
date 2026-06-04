import { httpClient } from '../http'
import type {
  ImportResult,
  InstalledScenariosResponseDTO,
  ScenarioDraftDTO,
  ScenarioActivateMode,
  ScenarioActivateResponse,
  ScenarioDebugSnapshotDTO,
  ScenarioGenerateResultDTO,
  ScenarioRuntimeResponse,
  ScenarioSaveDraftResultDTO,
  ScenarioStateUpdate,
  ScenarioStatusResponseDTO,
  ScenarioTemplatesResponseDTO,
} from '../../types/api'

export const scenarioApi = {
  fetchScenarioStatus() {
    return httpClient.get<ScenarioStatusResponseDTO>('/api/v1/query/scenario/status')
  },

  fetchInstalledScenarios() {
    return httpClient.get<InstalledScenariosResponseDTO>('/api/v1/query/scenarios')
  },

  fetchTemplates() {
    return httpClient.get<ScenarioTemplatesResponseDTO>('/api/v1/query/scenario/templates')
  },

  loadTemplate(category: string) {
    return httpClient.get<ScenarioDraftDTO>(`/api/v1/query/scenario/templates/${encodeURIComponent(category)}`)
  },

  generateScenario(description: string, hints: Record<string, unknown>) {
    return httpClient.post<ScenarioGenerateResultDTO>('/api/v1/command/scenario/generate', {
      description,
      hints,
    })
  },

  saveDraft(draft: ScenarioDraftDTO) {
    return httpClient.post<ScenarioSaveDraftResultDTO>('/api/v1/command/scenario/save-draft', draft)
  },

  importScenario(file: File, force = false, renameTo?: string) {
    const body = new FormData()
    body.append('file', file)
    const params = new URLSearchParams()
    if (force) params.set('force', 'true')
    if (renameTo) params.set('rename_to', renameTo)
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return httpClient.postForm<ImportResult>(`/api/v1/command/scenario/import${suffix}`, body)
  },

  removeScenario(scenarioId: string) {
    return httpClient.post<{ scenario_id: string; removed: boolean }>(
      '/api/v1/command/scenario/remove',
      { scenario_id: scenarioId },
    )
  },

  setScenarioEnabled(scenarioId: string, enabled: boolean) {
    return httpClient.post<ScenarioStateUpdate>(
      '/api/v1/command/scenario/set-enabled',
      { scenario_id: scenarioId, enabled },
    )
  },

  activateScenario(scenarioId: string, mode: ScenarioActivateMode) {
    return httpClient.post<ScenarioActivateResponse>(
      '/api/v1/command/scenario/activate',
      { scenario_id: scenarioId, mode },
    )
  },

  deactivateScenario() {
    return httpClient.post<ScenarioRuntimeResponse>('/api/v1/command/scenario/deactivate', {})
  },

  reloadScenario() {
    return httpClient.post<ScenarioRuntimeResponse>('/api/v1/command/scenario/reload', {})
  },

  fetchDebugSnapshot() {
    return httpClient.get<ScenarioDebugSnapshotDTO | { ok: false; error: string }>('/api/v1/query/scenario/debug')
  },
}
