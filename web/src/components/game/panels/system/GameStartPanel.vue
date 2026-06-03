<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NForm, NFormItem, NInputNumber, NButton, NInput, NSelect, useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'

import ScenarioBrowserModal from './ScenarioBrowserModal.vue'
import { useScenarioBrowserModal } from '@/composables/useScenarioBrowserModal'
import { useScenarioStore } from '@/stores/scenario'
import { useSettingStore } from '@/stores/setting'
import { logError } from '@/utils/appError'

const { t } = useI18n()
const settingStore = useSettingStore()
const scenarioStore = useScenarioStore()
const {
  showScenarioBrowser,
  openScenarioBrowser,
  selectScenario,
} = useScenarioBrowserModal()

defineProps<{
  readonly: boolean
}>()

const message = useMessage()
const loading = ref(false)

const scenarioOptions = computed(() => [
  { label: '默认游戏（无 scenario）', value: 'default' },
  ...scenarioStore.installedScenarios.map((scenario) => ({
    label: `${scenario.name} v${scenario.version}`,
    value: scenario.id,
  })),
])

const selectedScenarioValue = computed(() => settingStore.newGameDraft.scenario_id ?? 'default')

function updateScenarioId(value: string | null) {
  settingStore.updateNewGameDraft({ scenario_id: value ?? 'default' })
}

function selectScenarioFromBrowser(scenarioId: string) {
  selectScenario(scenarioId)
  settingStore.updateNewGameDraft({ scenario_id: scenarioId })
}

function updateScenarioBrowserShow(value: boolean) {
  showScenarioBrowser.value = value
}

async function startGame() {
  try {
    loading.value = true
    await settingStore.startGameWithDraft()
    message.success(t('game_start.messages.start_success'))
  } catch (e) {
    message.error(t('game_start.messages.start_failed'))
    logError('GameStartPanel start game', e)
    loading.value = false
  }
}

onMounted(() => {
  void scenarioStore.fetchInstalledScenarios()
})
</script>

<template>
  <div class="game-start-panel">
    <div class="panel-header">
      <h3>{{ t('game_start.title') }}</h3>
      <p class="description">{{ t('game_start.description') }}</p>
    </div>

    <n-form
      label-placement="left"
      label-width="160"
      require-mark-placement="right-hanging"
      :disabled="readonly"
    >
      <n-form-item :label="t('game_start.labels.init_npc_num')" path="init_npc_num">
        <n-input-number
          :value="settingStore.newGameDraft.init_npc_num"
          :min="0"
          :max="100"
          @update:value="(value) => settingStore.updateNewGameDraft({ init_npc_num: value ?? 0 })"
        />
      </n-form-item>

      <n-form-item :label="t('game_start.labels.sect_num')" path="sect_num">
        <n-input-number
          :value="settingStore.newGameDraft.sect_num"
          :min="0"
          :max="10"
          @update:value="(value) => settingStore.updateNewGameDraft({ sect_num: value ?? 0 })"
        />
      </n-form-item>
      <div class="tip-text" style="margin-top: -12px;">
        {{ t('game_start.tips.sect_num') }}
      </div>

      <n-form-item label="Scenario" path="scenario_id">
        <div class="scenario-picker">
          <n-select
            :value="selectedScenarioValue"
            :options="scenarioOptions"
            @update:value="updateScenarioId"
          />
          <n-button
            text
            type="primary"
            size="small"
            @click="openScenarioBrowser"
          >
            Browse
          </n-button>
        </div>
      </n-form-item>

      <n-form-item :label="t('game_start.labels.new_npc_rate')" path="npc_awakening_rate_per_month">
        <n-input-number
          :value="settingStore.newGameDraft.npc_awakening_rate_per_month"
          :min="0"
          :max="1"
          :step="0.001"
          :format="(val: number) => `${(val * 100).toFixed(1)}%`"
          :parse="(val: string) => parseFloat(val) / 100"
          @update:value="(value) => settingStore.updateNewGameDraft({ npc_awakening_rate_per_month: value ?? 0 })"
        />
      </n-form-item>

      <n-form-item :label="t('game_start.labels.world_lore')" path="world_lore">
        <n-input
          :value="settingStore.newGameDraft.world_lore"
          type="textarea"
          :placeholder="t('game_start.placeholders.world_lore')"
          :autosize="{ minRows: 4, maxRows: 6 }"
          maxlength="800"
          show-count
          @update:value="(value) => settingStore.updateNewGameDraft({ world_lore: value })"
        />
      </n-form-item>

      <div class="actions" v-if="!readonly">
        <n-button type="primary" size="large" @click="startGame" :loading="loading">
          {{ t('game_start.actions.start') }}
        </n-button>
      </div>
    </n-form>

    <ScenarioBrowserModal
      :show="showScenarioBrowser"
      @update:show="updateScenarioBrowserShow"
      @select="selectScenarioFromBrowser"
    />
  </div>
</template>

<style scoped>
.game-start-panel {
  color: #eee;
  max-width: 600px;
  margin: 0 auto;
}

.panel-header {
  margin-bottom: 2em;
  text-align: center;
}

.description {
  color: #888;
  font-size: 0.9em;
}

.tip-text {
  margin-left: 160px;
  margin-bottom: 24px;
  color: #aaa;
  font-size: 0.85em;
  line-height: 1.5;
}

.scenario-picker {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  width: 100%;
  align-items: center;
}

.actions {
  display: flex;
  justify-content: center;
  margin-top: 2em;
}
</style>
