<script setup lang="ts">
import { NModal, NSpin, NTag } from 'naive-ui'
import { useScenarioOverviewModal } from '@/composables/useScenarioOverviewModal'
import flagIcon from '@/assets/icons/ui/lucide/flag.svg'
import scrollIcon from '@/assets/icons/ui/lucide/scroll-text.svg'

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

function handleShowChange(value: boolean) {
  emit('update:show', value)
}
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
</template>

<style scoped>
.scenario-overview {
  display: flex;
  flex-direction: column;
  gap: 18px;
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
</style>
