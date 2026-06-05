import { httpClient } from '../http'
import type { ScenarioStatusResponseDTO } from '../../types/api'

export const scenarioApi = {
  fetchScenarioStatus() {
    return httpClient.get<ScenarioStatusResponseDTO>('/api/v1/query/scenario/status')
  },
}
