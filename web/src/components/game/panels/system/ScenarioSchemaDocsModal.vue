<script setup lang="ts">
import { NButton, NModal } from 'naive-ui'

defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (event: 'update:show', value: boolean): void
}>()
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="Scenario Schema Reference"
    class="scenario-schema-docs-modal"
    @update:show="(value: boolean) => emit('update:show', value)"
  >
    <div class="schema-docs">
      <section>
        <h3>scenario.json metadata</h3>
        <dl>
          <dt>scenario_id</dt>
          <dd>Required stable lower_snake_case id. It must match the scenario directory name.</dd>
          <dt>title</dt>
          <dd>Required display name shown in scenario browser.</dd>
          <dt>version</dt>
          <dd>Required content version string.</dd>
          <dt>description</dt>
          <dd>Required short browser summary.</dd>
          <dt>author / tags / cover_image</dt>
          <dd>Optional metadata used by discovery and browser cards.</dd>
        </dl>
      </section>

      <section>
        <h3>world_preset</h3>
        <p>
          Use an existing bundled preset id such as <code>default</code>, <code>liuchao</code>,
          or <code>sanguo</code>. Referenced realms, sects, personas, and goldfingers must exist
          in that preset.
        </p>
      </section>

      <section>
        <h3>initial_state</h3>
        <dl>
          <dt>year / month</dt>
          <dd>Optional starting date used when the scenario starts.</dd>
          <dt>avatars</dt>
          <dd>List of starter avatars. Each avatar needs a stable id and may reference preset data.</dd>
          <dt>relationships</dt>
          <dd>Pairs of avatar ids with a numeric relationship value.</dd>
          <dt>sects</dt>
          <dd>Optional starter sect membership using preset sect ids.</dd>
          <dt>world_flags</dt>
          <dd>Scenario flags available to timeline conditions.</dd>
        </dl>
      </section>

      <section>
        <h3>timeline.json</h3>
        <dl>
          <dt>events</dt>
          <dd>Each event needs id, type, trigger.year, and trigger.month.</dd>
          <dt>type</dt>
          <dd>Allowed values include main, world_event, character_introduction, relation_change, sect_event, side_event, and ending.</dd>
          <dt>effects</dt>
          <dd>Common starter effect: <code>{"type":"set_flag","flag":"flag_name"}</code>.</dd>
        </dl>
      </section>
    </div>
    <template #footer>
      <div class="scenario-schema-docs-footer">
        <n-button size="small" @click="emit('update:show', false)">Close</n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.scenario-schema-docs-modal {
  width: min(760px, calc(100vw - 32px));
}

.schema-docs {
  display: grid;
  gap: 16px;
  max-height: min(640px, calc(100vh - 180px));
  overflow: auto;
}

.schema-docs h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.schema-docs dl {
  display: grid;
  grid-template-columns: minmax(120px, 180px) 1fr;
  gap: 8px 12px;
  margin: 0;
}

.schema-docs dt {
  font-weight: 700;
}

.schema-docs dd,
.schema-docs p {
  margin: 0;
  color: rgba(255, 255, 255, 0.72);
}

.scenario-schema-docs-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
