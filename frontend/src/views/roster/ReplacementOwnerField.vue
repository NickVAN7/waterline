<script setup lang="ts">
// The replacement-owner picker (DL-59): shown once the server refuses a change because the person
// is the last owner, it searches the roster's other active people (`PersonPicker`, DL-422); the one
// chosen becomes owner first. The server checks the choice (`not_member`, `account_inactive`,
// `same_user`); its 422 shows here. The model is the chosen person's id, '' while there's none.
import { ref, watch } from 'vue'

import PersonPicker, { type Person } from '@/components/PersonPicker.vue'

import type { RosterPerson } from './roster'

const props = defineProps<{
  id: string
  /** Why it's needed: the server's own message for the refusal. */
  reason: string
  exclude: string
  search: (q: string) => Promise<RosterPerson[]>
  error?: string
}>()

const model = defineModel<string>({ required: true })
const person = ref<Person | null>(null)
watch(person, (p) => (model.value = p?.user_id ?? ''))
watch(model, (id) => {
  if (id !== (person.value?.user_id ?? '')) person.value = null
})
const picker = ref<InstanceType<typeof PersonPicker>>()
defineExpose({ focus: () => picker.value?.focus() })

// The roster lists active people only (DL-293); `is_active` is kept as a second check.
const others = async (q: string) =>
  (await props.search(q)).filter((p) => p.is_active && p.user_id !== props.exclude)
</script>

<template>
  <div class="flex flex-col gap-2">
    <!-- Read as focus lands on the picker (DL-118). -->
    <p :id="`${id}-reason`" class="m-0">{{ reason }}</p>
    <PersonPicker
      :id="id"
      ref="picker"
      v-model="person"
      label="New owner"
      help="Search by name, email, or username. They become an owner before this change is made."
      required
      :error="error"
      :described-by="`${id}-reason`"
      :search="others"
    />
  </div>
</template>
