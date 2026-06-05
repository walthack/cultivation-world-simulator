import { computed, watch } from 'vue'
import { SHARED_UI_COLORS } from '@/constants/uiColors'
import { useScenarioStore } from '@/stores/scenario'
import type { ScenarioTimelineEventDTO } from '@/types/api'

function byTriggerTime(left: ScenarioTimelineEventDTO, right: ScenarioTimelineEventDTO) {
  const leftYear = left.trigger.year ?? Number.MAX_SAFE_INTEGER
  const rightYear = right.trigger.year ?? Number.MAX_SAFE_INTEGER
  if (leftYear !== rightYear) return leftYear - rightYear
  const leftMonth = left.trigger.month ?? Number.MAX_SAFE_INTEGER
  const rightMonth = right.trigger.month ?? Number.MAX_SAFE_INTEGER
  return leftMonth - rightMonth
}

export function useScenarioOverviewModal(show: () => boolean) {
  const scenarioStore = useScenarioStore()
  const panelStyleVars = {
    '--panel-accent': '#caa45d',
    '--panel-accent-strong': '#f0cf86',
    '--panel-accent-soft': 'rgba(202, 164, 93, 0.16)',
    '--panel-title': '#f0cf86',
    '--panel-empty': '#8f8675',
    '--panel-border': 'rgba(202, 164, 93, 0.24)',
    '--panel-text-primary': SHARED_UI_COLORS.textPrimary,
    '--panel-text-secondary': SHARED_UI_COLORS.textSecondary,
  }

  const status = computed(() => scenarioStore.activeStatus)
  const hasScenario = computed(() => Boolean(status.value))
  const triggeredEvents = computed(() =>
    status.value?.timeline.events.filter((event) => event.triggered).sort(byTriggerTime) ?? [],
  )
  const untriggeredEvents = computed(() =>
    status.value?.timeline.events.filter((event) => !event.triggered).sort(byTriggerTime) ?? [],
  )

  function formatTrigger(event: ScenarioTimelineEventDTO) {
    const parts: string[] = []
    if (event.trigger.year !== null && event.trigger.year !== undefined) {
      parts.push(`Y${event.trigger.year}`)
    }
    if (event.trigger.month !== null && event.trigger.month !== undefined) {
      parts.push(`M${event.trigger.month}`)
    }
    return parts.join('') || '时间未标注'
  }

  function formatTriggeredAt(event: ScenarioTimelineEventDTO) {
    if (event.triggered_month_stamp) return `已触发于 ${event.triggered_month_stamp}`
    return `已触发于 ${formatTrigger(event)}`
  }

  watch(
    show,
    (isShown) => {
      if (isShown) {
        void scenarioStore.refreshStatus()
      }
    },
    { immediate: true },
  )

  return {
    scenarioStore,
    panelStyleVars,
    status,
    hasScenario,
    triggeredEvents,
    untriggeredEvents,
    formatTrigger,
    formatTriggeredAt,
  }
}
