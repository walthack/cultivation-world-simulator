import { httpClient } from '../http'
import type {
  ImportResult,
  InstalledScenariosResponseDTO,
  ScenarioStateUpdate,
  ScenarioStatusResponseDTO,
} from '../../types/api'

export const scenarioApi = {
  fetchScenarioStatus() {
    return httpClient.get<ScenarioStatusResponseDTO>('/api/v1/query/scenario/status')
  },

  fetchInstalledScenarios() {
    return httpClient.get<InstalledScenariosResponseDTO>('/api/v1/query/scenarios')
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
}
