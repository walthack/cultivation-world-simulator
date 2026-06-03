<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { NButton, NModal, useMessage } from 'naive-ui'
import { useScenarioWizard } from '@/composables/useScenarioWizard'
import type {
  ScenarioDraftAvatarDTO,
} from '@/types/api'
import ScenarioSchemaDocsModal from './ScenarioSchemaDocsModal.vue'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (event: 'update:show', value: boolean): void
  (event: 'saved', scenarioId: string): void
}>()

const message = useMessage()
const wizard = useScenarioWizard()
const selectedTemplate = ref('')
const generationDescription = ref('')
const showSchemaDocs = ref(false)

const scenario = computed(() => wizard.draft.value.scenario)
const initialState = computed(() => wizard.draft.value.scenario.initial_state)
const timeline = computed(() => wizard.draft.value.timeline)
const tagsText = computed({
  get: () => (scenario.value.tags || []).join(', '),
  set: (value: string) => {
    scenario.value.tags = value.split(',').map((tag) => tag.trim()).filter(Boolean)
  },
})

function close() {
  emit('update:show', false)
}

function addAvatar() {
  const index = initialState.value.avatars.length + 1
  initialState.value.avatars.push({
    id: `avatar-${index}`,
    surname: 'New',
    given_name: `Avatar ${index}`,
    gender: '男',
    age: 20,
    sect_id: null,
    realm: 'QI_REFINEMENT',
    stage: 'EARLY_STAGE',
    level: 1,
    persona_traits: ['RATIONAL'],
    goldfinger_id: 'CHILD_OF_FORTUNE',
    long_term_objective: '',
  })
}

function removeAvatar(index: number) {
  initialState.value.avatars.splice(index, 1)
}

function addRelationship() {
  const avatars = initialState.value.avatars
  initialState.value.relationships.push({
    a: avatars[0]?.id || '',
    b: avatars[1]?.id || '',
    value: 0,
    tag: '',
  })
}

function removeRelationship(index: number) {
  initialState.value.relationships.splice(index, 1)
}

function addEvent() {
  const index = timeline.value.events.length + 1
  timeline.value.events.push({
    id: `event-${index}`,
    type: 'main',
    trigger: { year: initialState.value.year || 1, month: initialState.value.month || 1 },
    name: `Event ${index}`,
    description: '',
    effects: [{ type: 'set_flag', flag: `event_${index}_seen` }],
  })
}

function removeEvent(index: number) {
  timeline.value.events.splice(index, 1)
}

function updatePersonaTraits(avatar: ScenarioDraftAvatarDTO, value: string) {
  avatar.persona_traits = value.split(',').map((item) => item.trim()).filter(Boolean)
}

function personaTraitsText(avatar: ScenarioDraftAvatarDTO): string {
  return (avatar.persona_traits || []).join(', ')
}

async function applyTemplate() {
  if (!selectedTemplate.value) return
  try {
    await wizard.applyTemplate(selectedTemplate.value)
    message.success('Template loaded')
  } catch (error) {
    message.error(error instanceof Error ? error.message : 'Template failed to load')
  }
}

async function generateScenario() {
  const description = generationDescription.value.trim()
  if (!description) {
    message.error('Description is required')
    return
  }
  const result = await wizard.generate(description, {
    preset_id: scenario.value.world_preset.preset_id || 'liuchao',
  })
  if (result.ok) {
    message.success('Scenario draft generated')
  } else {
    message.error(result.validation_errors.join('; ') || 'Generated draft failed validation')
  }
}

async function saveAndActivate() {
  const result = await wizard.saveAndActivate()
  if (!result) {
    message.error(wizard.validationMessage.value || 'Scenario draft is incomplete')
    return
  }
  message.success('Scenario saved')
  emit('saved', result.scenario_id)
}

async function exportZip() {
  const result = await wizard.exportZip()
  if (!result) {
    message.error(wizard.validationMessage.value || 'Scenario draft is incomplete')
    return
  }
  message.success('Scenario zip exported')
}

watch(
  () => props.show,
  (isShown) => {
    if (!isShown) return
    wizard.hydrateFromLocalStorage()
    void wizard.fetchTemplates()
  },
  { immediate: true },
)

onMounted(() => {
  wizard.hydrateFromLocalStorage()
})
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="Create Scenario"
    class="scenario-wizard-modal"
    @update:show="(value: boolean) => emit('update:show', value)"
  >
    <div class="scenario-wizard">
      <nav class="wizard-steps" aria-label="Scenario wizard steps">
        <button
          v-for="(step, index) in wizard.steps"
          :key="step"
          class="wizard-step"
          :class="{ active: index === wizard.currentStep.value }"
          type="button"
          @click="wizard.goToStep(index)"
        >
          <span>{{ index + 1 }}</span>
          {{ step }}
        </button>
      </nav>

      <div class="wizard-header-row">
        <h3>{{ wizard.stepName.value }}</h3>
        <n-button size="tiny" type="tertiary" @click="showSchemaDocs = true">?</n-button>
      </div>

      <p v-if="wizard.validationMessage.value" class="wizard-validation">
        {{ wizard.validationMessage.value }}
      </p>

      <section v-if="wizard.currentStep.value === 0" class="wizard-panel">
        <label>
          Scenario id
          <input v-model="scenario.scenario_id" placeholder="my_scenario">
        </label>
        <label>
          Title
          <input v-model="scenario.title" placeholder="Scenario title">
        </label>
        <label>
          Version
          <input v-model="scenario.version" placeholder="1.0">
        </label>
        <label>
          Author
          <input v-model="scenario.author" placeholder="Author">
        </label>
        <label class="wide">
          Description
          <textarea v-model="scenario.description" rows="3" placeholder="Short scenario summary" />
        </label>
        <label class="wide">
          Tags
          <input v-model="tagsText" placeholder="historical, starter">
        </label>
        <label class="wide">
          Start from Template
          <div class="inline-row">
            <select v-model="selectedTemplate">
              <option value="">Choose a template</option>
              <option
                v-for="template in wizard.templates.value"
                :key="template.category"
                :value="template.category"
              >
                {{ template.title }} - {{ template.summary }}
              </option>
            </select>
            <n-button size="small" @click="applyTemplate">Load</n-button>
          </div>
        </label>
      </section>

      <section v-else-if="wizard.currentStep.value === 1" class="wizard-panel">
        <label>
          World preset
          <select v-model="scenario.world_preset.preset_id">
            <option value="default">default</option>
            <option value="liuchao">liuchao</option>
            <option value="sanguo">sanguo</option>
          </select>
        </label>
        <label>
          Start year
          <input v-model.number="initialState.year" type="number" min="1">
        </label>
        <label>
          Start month
          <input v-model.number="initialState.month" type="number" min="1" max="12">
        </label>
        <label class="wide">
          World background
          <textarea v-model="scenario.world_background" rows="5" />
        </label>
      </section>

      <section v-else-if="wizard.currentStep.value === 2" class="wizard-panel single-column">
        <label>
          Describe your world
          <textarea
            v-model="generationDescription"
            rows="8"
            placeholder="Describe the setting, main characters, conflict, and timeline beats."
          />
        </label>
        <div class="inline-row">
          <n-button type="primary" :loading="wizard.isGenerating.value" @click="generateScenario">
            Generate
          </n-button>
          <span v-if="wizard.lastGenerateResult.value && !wizard.lastGenerateResult.value.ok" class="wizard-validation">
            {{ wizard.lastGenerateResult.value.validation_errors.join('; ') }}
          </span>
        </div>
      </section>

      <section v-else-if="wizard.currentStep.value === 3" class="wizard-panel single-column">
        <div class="section-toolbar">
          <h4>Avatars</h4>
          <n-button size="small" @click="addAvatar">Add Avatar</n-button>
        </div>
        <div
          v-for="(avatar, index) in initialState.avatars"
          :key="avatar.id || index"
          class="editor-row avatar-row"
        >
          <input v-model="avatar.id" placeholder="id">
          <input v-model="avatar.surname" placeholder="surname">
          <input v-model="avatar.given_name" placeholder="given name">
          <input v-model="avatar.realm" placeholder="realm">
          <input
            :value="personaTraitsText(avatar)"
            placeholder="persona traits"
            @input="updatePersonaTraits(avatar, ($event.target as HTMLInputElement).value)"
          >
          <n-button size="tiny" @click="removeAvatar(index)">Remove</n-button>
        </div>

        <div class="section-toolbar">
          <h4>Relations</h4>
          <n-button size="small" @click="addRelationship">Add Relation</n-button>
        </div>
        <div
          v-for="(relation, index) in initialState.relationships"
          :key="`${relation.a}-${relation.b}-${index}`"
          class="editor-row relation-row"
        >
          <input v-model="relation.a" placeholder="avatar a">
          <input v-model="relation.b" placeholder="avatar b">
          <input v-model.number="relation.value" type="number" placeholder="value">
          <input v-model="relation.tag" placeholder="tag">
          <n-button size="tiny" @click="removeRelationship(index)">Remove</n-button>
        </div>
      </section>

      <section v-else-if="wizard.currentStep.value === 4" class="wizard-panel single-column">
        <div class="section-toolbar">
          <h4>Timeline</h4>
          <n-button size="small" @click="addEvent">Add Event</n-button>
        </div>
        <div
          v-for="(event, index) in timeline.events"
          :key="event.id || index"
          class="editor-row event-row"
        >
          <input v-model="event.id" placeholder="event id">
          <select v-model="event.type">
            <option value="main">main</option>
            <option value="world_event">world_event</option>
            <option value="character_introduction">character_introduction</option>
            <option value="relation_change">relation_change</option>
            <option value="sect_event">sect_event</option>
            <option value="side_event">side_event</option>
            <option value="ending">ending</option>
          </select>
          <input v-model.number="event.trigger.year" type="number" min="1" placeholder="year">
          <input v-model.number="event.trigger.month" type="number" min="1" max="12" placeholder="month">
          <input v-model="event.name" placeholder="name">
          <textarea v-model="event.description" rows="2" placeholder="description" />
          <n-button size="tiny" @click="removeEvent(index)">Remove</n-button>
        </div>
      </section>

      <section v-else class="wizard-panel single-column">
        <div class="review-grid">
          <span>Scenario id</span><strong>{{ scenario.scenario_id }}</strong>
          <span>Title</span><strong>{{ scenario.title }}</strong>
          <span>Preset</span><strong>{{ scenario.world_preset.preset_id }}</strong>
          <span>Avatars</span><strong>{{ initialState.avatars.length }}</strong>
          <span>Relations</span><strong>{{ initialState.relationships.length }}</strong>
          <span>Events</span><strong>{{ timeline.events.length }}</strong>
        </div>
        <pre>{{ JSON.stringify(wizard.draft.value, null, 2) }}</pre>
      </section>
    </div>

    <template #footer>
      <div class="wizard-footer">
        <n-button size="small" @click="close">Cancel</n-button>
        <n-button size="small" :disabled="!wizard.canGoBack.value" @click="wizard.back">Back</n-button>
        <n-button
          v-if="!wizard.isLastStep.value"
          size="small"
          type="primary"
          @click="wizard.next"
        >
          Next
        </n-button>
        <n-button
          v-else
          size="small"
          type="primary"
          :loading="wizard.isSaving.value"
          @click="saveAndActivate"
        >
          Save & Activate
        </n-button>
        <n-button size="small" :loading="wizard.isSaving.value" @click="exportZip">Export .zip</n-button>
      </div>
    </template>
  </n-modal>

  <scenario-schema-docs-modal v-model:show="showSchemaDocs" />
</template>

<style scoped>
.scenario-wizard-modal {
  width: min(980px, calc(100vw - 32px));
}

.scenario-wizard {
  display: grid;
  gap: 16px;
}

.wizard-steps {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 6px;
}

.wizard-step {
  min-height: 40px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
  cursor: pointer;
}

.wizard-step.active {
  border-color: #7aa2f7;
  background: rgba(122, 162, 247, 0.16);
}

.wizard-step span {
  display: inline-grid;
  width: 20px;
  height: 20px;
  place-items: center;
  margin-right: 4px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
}

.wizard-header-row,
.section-toolbar,
.wizard-footer,
.inline-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.wizard-header-row,
.section-toolbar,
.wizard-footer {
  justify-content: space-between;
}

.wizard-header-row h3,
.section-toolbar h4 {
  margin: 0;
}

.wizard-panel {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  max-height: min(620px, calc(100vh - 260px));
  overflow: auto;
}

.wizard-panel.single-column {
  grid-template-columns: 1fr;
}

.wizard-panel label {
  display: grid;
  gap: 6px;
  font-size: 13px;
}

.wizard-panel .wide {
  grid-column: 1 / -1;
}

input,
select,
textarea {
  width: 100%;
  min-height: 34px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 6px;
  padding: 6px 8px;
  background: rgba(0, 0, 0, 0.18);
  color: inherit;
  box-sizing: border-box;
}

textarea {
  resize: vertical;
}

.editor-row {
  display: grid;
  gap: 8px;
  align-items: start;
}

.avatar-row {
  grid-template-columns: 1fr 1fr 1fr 1fr 1fr auto;
}

.relation-row {
  grid-template-columns: 1fr 1fr 110px 1fr auto;
}

.event-row {
  grid-template-columns: 1fr 150px 80px 80px 1fr 1.5fr auto;
}

.review-grid {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 8px 12px;
}

pre {
  max-height: 260px;
  overflow: auto;
  padding: 12px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.2);
}

.wizard-validation {
  margin: 0;
  color: #ffb4a8;
}

@media (max-width: 760px) {
  .wizard-steps,
  .wizard-panel,
  .avatar-row,
  .relation-row,
  .event-row {
    grid-template-columns: 1fr;
  }
}
</style>
