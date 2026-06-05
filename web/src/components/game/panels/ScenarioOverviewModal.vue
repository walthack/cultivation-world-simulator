<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NButton, NModal, NSelect, NSpin, NTabPane, NTag, NTabs } from 'naive-ui'
import { useScenarioOverviewModal } from '@/composables/useScenarioOverviewModal'
import { useSettingStore } from '@/stores/setting'
import type { ScenarioActivateMode } from '@/types/api'
import flagIcon from '@/assets/icons/ui/lucide/flag.svg'
import scrollIcon from '@/assets/icons/ui/lucide/scroll-text.svg'

const HOT_SWAP_WARNING = 'Hot-swap does not re-anchor time. Events scheduled before the current world time will not fire.'

const props = defineProps<{
  show: boolean;
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void;
}>()

const {
  scenarioStore,
  panelStyleVars,
  status,
  hasScenario,
  triggeredEvents,
  untriggeredEvents,
  formatTrigger,
  formatTriggeredAt,
} = useScenarioOverviewModal(() => props.show)
const settingStore = useSettingStore()
const selectedScenarioId = ref<string | null>(null)
const activationMode = ref<ScenarioActivateMode>('reset')
const showActivateConfirm = ref(false)
const showDeactivateConfirm = ref(false)

const advancedRuntimeControl = computed(() => settingStore.advancedRuntimeControl)
const scenarioOptions = computed(() =>
  scenarioStore.installedScenarios
    .filter((scenario) => scenario.enabled)
    .map((scenario) => ({
      label: `${scenario.name} (${scenario.id})`,
      value: scenario.id,
    })),
)
const debugStateEntries = computed(() => Object.entries(scenarioStore.debugSnapshot.state ?? {}))

function handleShowChange(value: boolean) {
  emit('update:show', value)
}

function requestActivate(mode: ScenarioActivateMode) {
  activationMode.value = mode
  showActivateConfirm.value = true
}

async function confirmActivate() {
  if (!selectedScenarioId.value) return
  await scenarioStore.activateScenario(selectedScenarioId.value, activationMode.value)
  showActivateConfirm.value = false
}

async function confirmDeactivate() {
  await scenarioStore.deactivateScenario()
  showDeactivateConfirm.value = false
}

async function reloadScenario() {
  await scenarioStore.reloadScenario()
}

function formatDebugValue(value: unknown) {
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}

watch(
  () => props.show,
  (isShown) => {
    if (!isShown) return
    void scenarioStore.fetchInstalledScenarios()
    if (advancedRuntimeControl.value) {
      void scenarioStore.refreshDebugSnapshot()
    }
  },
  { immediate: true },
)

watch(
  scenarioOptions,
  (options) => {
    if (selectedScenarioId.value && options.some((option) => option.value === selectedScenarioId.value)) return
    selectedScenarioId.value = options[0]?.value ?? null
  },
  { immediate: true },
)
</script>

<template>
  <n-modal
    :show="show"
    @update:show="handleShowChange"
    preset="card"
    title="剧本"
    style="width: 760px; max-height: 80vh; overflow-y: auto;"
  >
    <n-spin :show="scenarioStore.isLoading">
      <div class="scenario-overview" :style="panelStyleVars">
        <section v-if="advancedRuntimeControl" class="runtime-controls">
          <n-select
            v-model:value="selectedScenarioId"
            :options="scenarioOptions"
            placeholder="选择剧本"
            class="scenario-select"
          />
          <n-button size="small" type="primary" :disabled="!selectedScenarioId" @click="requestActivate('reset')">Activate reset</n-button>
          <n-button size="small" type="warning" :disabled="!selectedScenarioId" @click="requestActivate('hot-swap')">Activate hot-swap</n-button>
          <n-button size="small" :disabled="!hasScenario" @click="reloadScenario">Reload</n-button>
          <n-button size="small" type="error" :disabled="!hasScenario" @click="showDeactivateConfirm = true">Deactivate</n-button>
        </section>

        <template v-if="hasScenario && status">
          <section class="hero-card">
            <div class="hero-header">
              <div class="hero-title-wrap">
                <span class="hero-icon" :style="{ '--icon-url': `url(${scrollIcon})` }" aria-hidden="true"></span>
                <div class="hero-text">
                  <div class="hero-title">{{ status.title }}</div>
                  <div class="hero-subtitle">v{{ status.version }} · preset: {{ status.preset_id }}</div>
                </div>
              </div>
              <n-tag size="small" :bordered="false" type="warning">
                {{ status.timeline.triggered_count }} / {{ status.timeline.total_events }}
              </n-tag>
            </div>
            <div class="hero-desc">{{ status.world_background }}</div>
          </section>

          <n-tabs type="line" animated>
            <n-tab-pane name="timeline" tab="Timeline">
              <section class="section">
                <div class="section-title">
                  <span class="section-title-icon" :style="{ '--icon-url': `url(${flagIcon})` }" aria-hidden="true"></span>
                  已触发事件
                </div>
                <div v-if="triggeredEvents.length" class="event-list event-list--triggered">
                  <div v-for="event in triggeredEvents" :key="event.id" class="event-row event-row--triggered">
                    <div class="event-main">
                      <div class="event-name">{{ event.name }}</div>
                      <div class="event-id">{{ event.id }}</div>
                    </div>
                    <div class="event-meta">
                      <span>{{ formatTriggeredAt(event) }}</span>
                      <span v-if="event.dynasty_id">dynasty: {{ event.dynasty_id }}</span>
                      <span v-if="event.at_region_id">region: {{ event.at_region_id }}</span>
                    </div>
                  </div>
                </div>
                <div v-else class="empty-state section-empty">暂无已触发事件</div>
              </section>

              <section class="section">
                <div class="section-title">
                  <span class="section-title-icon" :style="{ '--icon-url': `url(${flagIcon})` }" aria-hidden="true"></span>
                  未触发事件
                </div>
                <div v-if="untriggeredEvents.length" class="event-list">
                  <div v-for="event in untriggeredEvents" :key="event.id" class="event-row event-row--pending">
                    <div class="event-main">
                      <div class="event-name">{{ event.name }}</div>
                      <div class="event-id">{{ event.id }}</div>
                    </div>
                    <div class="event-meta">
                      <span>{{ formatTrigger(event) }}</span>
                      <span v-if="event.dynasty_id">dynasty: {{ event.dynasty_id }}</span>
                      <span v-if="event.at_region_id">region: {{ event.at_region_id }}</span>
                    </div>
                  </div>
                </div>
                <div v-else class="empty-state section-empty">暂无未触发事件</div>
              </section>
            </n-tab-pane>

            <n-tab-pane v-if="advancedRuntimeControl" name="debug" tab="Debug">
              <n-spin :show="scenarioStore.isDebugLoading">
                <section class="section">
                  <div class="section-title">State vars</div>
                  <div v-if="debugStateEntries.length" class="debug-table">
                    <div v-for="[key, value] in debugStateEntries" :key="key" class="debug-row">
                      <span class="debug-key">{{ key }}</span>
                      <span class="debug-value">{{ formatDebugValue(value) }}</span>
                    </div>
                  </div>
                  <div v-else class="empty-state section-empty">No state vars</div>
                </section>

                <section class="section">
                  <div class="section-title">Triggered events</div>
                  <div v-if="scenarioStore.debugSnapshot.triggered_events.length" class="debug-list">
                    <span v-for="eventId in scenarioStore.debugSnapshot.triggered_events" :key="eventId" class="debug-pill">{{ eventId }}</span>
                  </div>
                  <div v-else class="empty-state section-empty">No triggered events</div>
                </section>

                <section class="section">
                  <div class="section-title">Dispatch log</div>
                  <div v-if="scenarioStore.debugSnapshot.dispatch_log.length" class="event-list">
                    <div v-for="(entry, idx) in scenarioStore.debugSnapshot.dispatch_log" :key="`${entry.month_stamp}-${entry.event_id}-${idx}`" class="event-row">
                      <div class="event-main">
                        <div class="event-name">{{ entry.event_id }}</div>
                        <div class="event-id">{{ entry.reason || 'fired' }}</div>
                      </div>
                      <div class="event-meta">
                        <span>{{ entry.month_stamp }}</span>
                        <span>{{ entry.fired ? 'fired' : 'skipped' }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-else class="empty-state section-empty">No dispatch log</div>
                </section>
              </n-spin>
            </n-tab-pane>
          </n-tabs>

          <footer v-if="status.controlled_avatar" class="scenario-footer">
            当前接管: {{ status.controlled_avatar }}
          </footer>
        </template>

        <div v-else class="empty-state">
          当前无启用剧本
        </div>
      </div>
    </n-spin>
  </n-modal>

  <n-modal
    :show="showActivateConfirm"
    preset="dialog"
    title="Activate scenario"
    positive-text="Confirm"
    negative-text="Cancel"
    @positive-click="confirmActivate"
    @negative-click="showActivateConfirm = false"
    @close="showActivateConfirm = false"
  >
    <p>Activate {{ selectedScenarioId }} with {{ activationMode }} mode?</p>
    <p v-if="activationMode === 'hot-swap'" class="warning-text">{{ HOT_SWAP_WARNING }}</p>
  </n-modal>

  <n-modal
    :show="showDeactivateConfirm"
    preset="dialog"
    title="Deactivate scenario"
    positive-text="Deactivate"
    negative-text="Cancel"
    @positive-click="confirmDeactivate"
    @negative-click="showDeactivateConfirm = false"
    @close="showDeactivateConfirm = false"
  >
    <p>Deactivate the active scenario? Existing avatars stay in the world.</p>
  </n-modal>
</template>

<style scoped>
.scenario-overview {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.runtime-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.scenario-select {
  min-width: 240px;
  flex: 1 1 260px;
}

.hero-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(202, 164, 93, 0.25), rgba(55, 39, 18, 0.16)),
    rgba(255, 255, 255, 0.03);
}

.hero-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.hero-title-wrap {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}

.hero-text {
  min-width: 0;
}

.hero-icon {
  width: 28px;
  height: 28px;
  color: var(--panel-accent-strong);
  margin-top: 2px;
}

.hero-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--panel-text-primary);
}

.hero-subtitle {
  font-size: 13px;
  color: var(--panel-text-secondary);
  margin-top: 4px;
}

.hero-desc {
  color: var(--panel-text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: var(--panel-title);
  border-bottom: 1px solid var(--panel-border);
  padding-bottom: 6px;
}

.hero-icon,
.section-title-icon {
  display: inline-block;
  background-color: currentColor;
  -webkit-mask-image: var(--icon-url);
  mask-image: var(--icon-url);
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center;
  mask-position: center;
  -webkit-mask-size: contain;
  mask-size: contain;
}

.section-title-icon {
  width: 15px;
  height: 15px;
}

.event-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.event-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
}

.event-row--triggered {
  background: var(--panel-accent-soft);
}

.event-row--pending {
  opacity: 0.58;
}

.event-main {
  min-width: 0;
}

.event-name {
  color: var(--panel-text-primary);
  font-weight: 700;
  line-height: 1.35;
}

.event-id {
  margin-top: 3px;
  color: var(--panel-text-secondary);
  font-size: 12px;
  line-height: 1.35;
}

.event-meta {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
  color: var(--panel-text-secondary);
  font-size: 12px;
  line-height: 1.35;
}

.scenario-footer {
  align-self: flex-start;
  padding: 5px 9px;
  border: 1px solid var(--panel-border);
  border-radius: 4px;
  color: var(--panel-accent-strong);
  background: var(--panel-accent-soft);
  font-size: 12px;
}

.empty-state {
  color: var(--panel-empty);
  text-align: center;
  padding: 24px 12px;
}

.section-empty {
  padding: 10px 12px;
  text-align: left;
  border: 1px dashed var(--panel-border);
  border-radius: 6px;
}

.debug-table,
.debug-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.debug-row {
  display: grid;
  grid-template-columns: minmax(120px, 0.4fr) minmax(0, 1fr);
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
}

.debug-key {
  color: var(--panel-accent-strong);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.debug-value {
  color: var(--panel-text-secondary);
  font-size: 12px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.debug-list {
  flex-direction: row;
  flex-wrap: wrap;
}

.debug-pill {
  padding: 4px 8px;
  border: 1px solid var(--panel-border);
  border-radius: 4px;
  color: var(--panel-text-primary);
  background: rgba(255, 255, 255, 0.03);
  font-size: 12px;
}

.warning-text {
  color: #f0cf86;
  line-height: 1.6;
}
</style>
