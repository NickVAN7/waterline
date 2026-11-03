<script setup lang="ts">
// Creating a requirement in a dialog (build plan S2-C17a, S2-C18a; UI-SHL-12): the create form,
// with **Open as a full page**, which carries what was typed to `…/requirements/new`. Created, the
// dialog lands on the new requirement's page (DL-250). The page hears of a 403 (`refused`) and of
// a gone parent (`stale`), as the form says.
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import type { components } from '@/api/schema'
import Button from '@/components/Button.vue'
import ModalDialog from '@/components/ModalDialog.vue'

import CreateRequirementForm from './CreateRequirementForm.vue'

type Item = components['schemas']['RequirementItem']
type Requirement = components['schemas']['RequirementRead']
type ProjectType = components['schemas']['ProjectType']

const props = defineProps<{
  projectKey: string
  projectType: ProjectType
  items: Item[]
  fallbackFocus?: () => void
}>()
const emit = defineEmits<{ refused: []; stale: [] }>()

const router = useRouter()
const dialog = ref<InstanceType<typeof ModalDialog>>()
const form = ref<InstanceType<typeof CreateRequirementForm>>()
// Each opening starts the form afresh: the template, and the editor on Write.
const openings = ref(0)

async function open(): Promise<void> {
  openings.value += 1
  await dialog.value?.open()
}

// Focus goes to the page that opens, not back to New requirement.
async function created(requirement: Requirement) {
  dialog.value?.close({ returnFocus: false })
  await router.push({
    name: 'project-requirement',
    params: { key: props.projectKey, number: requirement.number },
  })
}

// Not while a create is sending: the page it lands on would hold a draft already created.
async function expand() {
  if (form.value!.pending) return
  const draft = { ...form.value!.values }
  dialog.value?.close({ returnFocus: false })
  await router.push({
    name: 'project-requirement-new',
    params: { key: props.projectKey },
    state: { draft },
  })
}

defineExpose({ open })
</script>

<template>
  <ModalDialog ref="dialog" title="Create a requirement" :fallback-focus="fallbackFocus">
    <CreateRequirementForm
      ref="form"
      :key="openings"
      :project-key="projectKey"
      :project-type="projectType"
      :items="items"
      @created="created"
      @refused="emit('refused')"
      @stale="emit('stale')"
    >
      <Button variant="secondary" @click="expand">Open as a full page</Button>
      <Button variant="secondary" @click="dialog?.close()">Cancel</Button>
    </CreateRequirementForm>
  </ModalDialog>
</template>
