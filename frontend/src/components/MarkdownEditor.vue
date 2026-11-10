<script setup lang="ts">
// A labelled markdown textarea with Write and Preview tabs, previewing with the saved view's
// renderer (UI-MD-2, DL-141). `focus()` returns to Write first, for a failed submit (UI-FRM-6).
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import { nextTick, ref } from 'vue'

import FormField from './FormField.vue'
import MarkdownView from './MarkdownView.vue'

withDefaults(
  defineProps<{
    id: string
    label: string
    required?: boolean
    help?: string
    error?: string
  }>(),
  { required: false, help: undefined, error: undefined },
)

const model = defineModel<string>({ required: true })
const tab = ref<string | number>('write')
const textarea = ref<HTMLTextAreaElement>()

defineExpose({
  focus: async () => {
    tab.value = 'write'
    await nextTick()
    textarea.value?.focus()
  },
})
</script>

<template>
  <FormField :id="id" :label="label" :required="required" :help="help" :error="error">
    <template #default="{ describedBy, invalid }">
      <Tabs v-model:value="tab">
        <TabList :pt="{ content: { 'aria-label': label } }">
          <Tab value="write">Write</Tab>
          <Tab value="preview">Preview</Tab>
        </TabList>
        <TabPanels class="px-0 pb-0">
          <!-- Not a tab stop: it holds the textarea (the APG tabs pattern). -->
          <TabPanel value="write" :pt="{ root: { tabindex: -1 } }">
            <textarea
              :id="id"
              ref="textarea"
              v-model="model"
              :name="id"
              rows="8"
              :aria-required="required ? 'true' : undefined"
              :aria-invalid="invalid ? 'true' : undefined"
              :aria-describedby="describedBy"
              :class="[
                'w-full resize-y rounded-md bg-bg p-2 text-text',
                invalid ? 'border-2 border-tone-danger-edge' : 'border border-border',
              ]"
            />
          </TabPanel>
          <TabPanel value="preview">
            <!-- Rendered only while shown, so typing doesn't re-render a hidden preview; the
                 panels stay mounted, so the textarea keeps its undo history and size. -->
            <template v-if="tab === 'preview'">
              <MarkdownView v-if="model.trim()" :source="model" />
              <p v-else class="m-0 text-text-muted">Nothing to preview.</p>
            </template>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </template>
  </FormField>
</template>
