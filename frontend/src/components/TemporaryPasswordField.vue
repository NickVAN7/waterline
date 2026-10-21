<script setup lang="ts">
// The temporary password before saving (UI-FRM-11): an editable field pre-filled with a generated
// password, and "Generate another". Shown as text: the admin reads it to pass it on. The policy's
// minimum length comes from the server (DL-91), never a number in the code.
import { onMounted, ref, watch } from 'vue'

import { generateTemporaryPassword } from '@/composables/temporaryPassword'
import { usePasswordPolicy } from '@/composables/usePasswordPolicy'

import Button from './Button.vue'
import FormField from './FormField.vue'

withDefaults(defineProps<{ id: string; error?: string }>(), { error: undefined })

const model = defineModel<string>({ required: true })
const { requirements } = usePasswordPolicy()
const input = ref<HTMLInputElement>()
defineExpose({ focus: () => input.value?.focus() })

function minimum(): number {
  return requirements.value.find((r) => r.code === 'too_short')?.value ?? 0
}

// The last password generated here: one the admin hasn't edited may be replaced.
let generated = ''

function generate(): void {
  generated = generateTemporaryPassword(minimum())
  model.value = generated
}

onMounted(() => {
  if (!model.value) generate()
})
// A minimum longer than the generated password, arriving after it was made, replaces it.
watch(requirements, () => {
  if (model.value === generated && generated.length < minimum()) generate()
})
</script>

<template>
  <FormField
    :id="id"
    label="Temporary password"
    required
    help="Generated for you; you may replace it. The person must change it when they first sign in."
    :error="error"
  >
    <template #default="{ describedBy, invalid }">
      <div class="flex flex-wrap items-center gap-2">
        <input
          :id="id"
          ref="input"
          v-model="model"
          type="text"
          :name="id"
          autocomplete="off"
          spellcheck="false"
          aria-required="true"
          :aria-invalid="invalid ? 'true' : undefined"
          :aria-describedby="describedBy"
          :class="[
            'min-h-(--control-height) min-w-0 flex-1 rounded-md bg-bg px-3 font-mono text-text',
            invalid ? 'border-2 border-tone-danger-edge' : 'border border-border',
          ]"
        />
        <Button variant="secondary" @click="generate">Generate another</Button>
      </div>
    </template>
  </FormField>
</template>
