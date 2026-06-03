import { httpClient } from '../http'
import type { InstalledScenariosResponseDTO, ScenarioStatusResponseDTO } from '../../types/api'

export const scenarioApi = {
  fetchScenarioStatus() {
    return httpClient.get<ScenarioStatusResponseDTO>('/api/v1/query/scenario/status')
  },

  fetchInstalledScenarios() {
    return httpClient.get<InstalledScenariosResponseDTO>('/api/v1/query/scenarios')
  },
}
