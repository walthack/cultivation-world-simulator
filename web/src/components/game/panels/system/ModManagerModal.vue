<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { systemApi } from '@/api/modules/system'
import type { InstalledModDTO, ModConflictDTO, ModExtensionDTO } from '@/types/api'

const tabs = ['Installed mods', 'Downloaded mods', 'Load Order', 'Extensions'] as const
type TabName = typeof tabs[number]

const activeTab = ref<TabName>('Installed mods')
const mods = ref<InstalledModDTO[]>([])
const loadOrder = ref<string[]>([])
const extensions = ref<ModExtensionDTO[]>([])
const conflicts = ref<ModConflictDTO[]>([])
const loading = ref(false)
const errorText = ref('')
const draggedModId = ref('')

const orderedMods = computed(() => {
  const byId = new Map(mods.value.map((mod) => [mod.mod_id, mod]))
  return loadOrder.value.map((id) => byId.get(id)).filter((mod): mod is InstalledModDTO => Boolean(mod))
})

function extensionList(mod: InstalledModDTO) {
  const ext = mod.extensions || {}
  const rules = (ext.rules || {}) as { predicates?: string[]; effects?: string[] }
  const assets = (ext.assets || {}) as { portraits?: string[]; icons?: string[]; localizations?: Record<string, string> }
  const llm = (ext.llm || {}) as { prompts?: Array<{ key: string }> }
  const code = (ext.code || {}) as { hooks?: string[] }
  return [
    ...(rules.predicates || []).map((name) => `predicate:${name}`),
    ...(rules.effects || []).map((name) => `effect:${name}`),
    ...(assets.portraits || []).map((name) => `asset:${name}`),
    ...(assets.icons || []).map((name) => `asset:${name}`),
    ...Object.keys(assets.localizations || {}).map((name) => `locale:${name}`),
    ...(llm.prompts || []).map((item) => `llm:${item.key}`),
    ...(code.hooks || []).map((name) => `hook:${name}`),
  ]
}

async function refresh() {
  loading.value = true
  errorText.value = ''
  try {
    const [installed, order, active] = await Promise.all([
      systemApi.fetchInstalledMods(),
      systemApi.fetchModLoadOrder(),
      systemApi.fetchActiveModExtensions(),
    ])
    mods.value = installed.mods
    conflicts.value = installed.conflicts || []
    loadOrder.value = order.load_order
    extensions.value = active.extensions
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : 'Failed to load mods'
  } finally {
    loading.value = false
  }
}

async function setEnabled(mod: InstalledModDTO, enabled: boolean) {
  mod.enabled = enabled
  try {
    await systemApi.setModEnabled(mod.mod_id, enabled)
    await refresh()
  } catch (error) {
    mod.enabled = !enabled
    errorText.value = error instanceof Error ? error.message : 'Failed to update mod'
    conflicts.value = extractConflicts(error)
  }
}

async function removeMod(mod: InstalledModDTO) {
  await systemApi.uninstallMod(mod.mod_id)
  await refresh()
}

function onDragStart(modId: string) {
  draggedModId.value = modId
}

async function onDrop(targetModId: string) {
  const source = draggedModId.value
  draggedModId.value = ''
  if (!source || source === targetModId) return
  const next = loadOrder.value.filter((id) => id !== source)
  const targetIndex = next.indexOf(targetModId)
  next.splice(targetIndex < 0 ? next.length : targetIndex, 0, source)
  loadOrder.value = next
  await systemApi.reorderMods(next)
  await refresh()
}

function extractConflicts(error: unknown): ModConflictDTO[] {
  const response = (error as { response?: { data?: { detail?: { details?: { conflicts?: ModConflictDTO[] } } } } }).response
  return response?.data?.detail?.details?.conflicts || []
}

onMounted(refresh)
</script>

<template>
  <div class="mod-manager">
    <header class="manager-header">
      <h3>Mod Manager</h3>
      <button type="button" @click="refresh">Refresh</button>
    </header>

    <div class="tab-row">
      <button
        v-for="tab in tabs"
        :key="tab"
        type="button"
        :class="{ active: activeTab === tab }"
        @click="activeTab = tab"
      >
        {{ tab }}
      </button>
    </div>

    <div v-if="errorText" class="error-text">{{ errorText }}</div>
    <div v-if="loading" class="state-text">Loading...</div>

    <section v-if="activeTab === 'Installed mods'" class="mod-grid">
      <article v-for="mod in mods" :key="mod.mod_id" class="mod-card">
        <div class="mod-card-header">
          <div>
            <h4>{{ mod.name }}</h4>
            <p>{{ mod.version }} · {{ mod.author || 'Unknown author' }}</p>
          </div>
          <span
            v-if="mod.python_hooks_declared"
            class="python-badge"
            :class="{ enabled: mod.python_hooks_enabled }"
          >
            Python hooks: {{ mod.python_hooks_enabled ? 'enabled' : 'disabled' }}
          </span>
        </div>
        <p class="description">{{ mod.description }}</p>
        <p class="fingerprint">{{ mod.fingerprint }}</p>
        <div class="extension-list">
          <span v-for="item in extensionList(mod)" :key="item">{{ item }}</span>
        </div>
        <div class="card-actions">
          <label>
            <input type="checkbox" :checked="mod.enabled" @change="setEnabled(mod, ($event.target as HTMLInputElement).checked)" />
            Enabled
          </label>
          <button type="button" @click="removeMod(mod)">Remove</button>
        </div>
      </article>
    </section>

    <section v-else-if="activeTab === 'Downloaded mods'" class="empty-pane">
      <p>Local .mod install is available through the v1 command API. Online marketplace is out of scope for v1.0.</p>
    </section>

    <section v-else-if="activeTab === 'Load Order'" class="load-order">
      <div
        v-for="mod in orderedMods"
        :key="mod.mod_id"
        class="order-row"
        draggable="true"
        @dragstart="onDragStart(mod.mod_id)"
        @dragover.prevent
        @drop="onDrop(mod.mod_id)"
      >
        <span class="drag-handle">::</span>
        <span>{{ mod.name }}</span>
        <span>{{ mod.mod_id }}</span>
      </div>
    </section>

    <section v-else class="extensions-pane">
      <div v-for="extension in extensions" :key="`${extension.mod_id}:${extension.kind}:${extension.name}`" class="extension-row">
        <span>{{ extension.mod_id }}</span>
        <span>{{ extension.kind }}</span>
        <strong>{{ extension.name }}</strong>
        <em>{{ extension.python_required ? 'Python' : 'data-only' }}</em>
        <span>{{ extension.inert ? 'inert' : 'active' }}</span>
      </div>
    </section>

    <div v-if="conflicts.length" class="conflict-modal">
      <div class="conflict-box">
        <h4>Mod conflict</h4>
        <p v-for="conflict in conflicts" :key="`${conflict.kind}:${conflict.name}`">
          {{ conflict.kind }} {{ conflict.name }}: {{ conflict.mod_ids.join(', ') }}
        </p>
        <button type="button" @click="conflicts = []">Close</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mod-manager {
  display: flex;
  flex-direction: column;
  gap: 16px;
  color: #eee;
}

.manager-header,
.mod-card-header,
.card-actions,
.tab-row,
.order-row,
.extension-row {
  display: flex;
  align-items: center;
}

.manager-header,
.mod-card-header,
.card-actions {
  justify-content: space-between;
  gap: 12px;
}

h3,
h4,
p {
  margin: 0;
}

button {
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 6px;
  background: #242424;
  color: #eee;
  padding: 8px 12px;
  cursor: pointer;
}

.tab-row {
  gap: 8px;
}

.tab-row button.active {
  border-color: #7fb2ff;
  color: #fff;
}

.mod-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.mod-card,
.empty-pane,
.load-order,
.extensions-pane {
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  padding: 14px;
}

.python-badge {
  border-radius: 999px;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.1);
  color: #bbb;
  font-size: 12px;
}

.python-badge.enabled {
  background: rgba(255, 176, 76, 0.18);
  color: #ffd197;
}

.description {
  color: #bbb;
  margin-top: 10px;
}

.fingerprint {
  color: #888;
  font-size: 12px;
  overflow-wrap: anywhere;
  margin-top: 8px;
}

.extension-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.extension-list span {
  border-radius: 999px;
  background: rgba(127, 178, 255, 0.12);
  padding: 3px 7px;
  color: #cfe1ff;
  font-size: 12px;
}

.load-order,
.extensions-pane {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.order-row,
.extension-row {
  gap: 12px;
  padding: 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.06);
}

.drag-handle {
  color: #999;
  cursor: grab;
}

.error-text {
  color: #ffb2b2;
}

.state-text {
  color: #aaa;
}

.conflict-modal {
  position: fixed;
  inset: 0;
  z-index: 1300;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.65);
}

.conflict-box {
  width: min(560px, 92vw);
  padding: 22px;
  border-radius: 8px;
  border: 1px solid rgba(255, 176, 76, 0.45);
  background: #181818;
}
</style>
