<script setup lang="ts">
// A requirement's status menu (DL-148): any status but its own and Approved, which comes only by
// hand (S2-C20) or through a completed approval request; the server decides each change. One
// menu button named with the requirement ("Change status of ERP-RQ-7"), opening PrimeVue's Menu
// (UI-STY-3), its change pending on the button (UI-FRM-8).
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import { computed, ref, useId } from 'vue'

import type { components } from '@/api/schema'
import { REQUIREMENT_STATUS } from '@/app/labels'
import Button from '@/components/Button.vue'

type Status = components['schemas']['RequirementStatus']

const props = defineProps<{ name: string; status: Status; pending?: boolean }>()
const emit = defineEmits<{ change: [status: Status] }>()

const id = useId()
const menu = ref<InstanceType<typeof Menu>>()
const root = ref<HTMLElement>()
const expanded = ref(false)
defineExpose({ focus: () => root.value?.querySelector('button')?.focus() })

const items = computed<MenuItem[]>(() =>
  (Object.keys(REQUIREMENT_STATUS) as Status[])
    .filter((status) => status !== props.status && status !== 'approved')
    .map((status) => ({
      label: REQUIREMENT_STATUS[status].label,
      // Focus goes back to the button first: the menu item that has it is about to go.
      command: () => {
        root.value?.querySelector('button')?.focus()
        emit('change', status)
      },
    })),
)
// PrimeVue sets `aria-level`, which a menu item may not have (axe `aria-allowed-attr`).
const pt = { item: () => ({ 'aria-level': undefined }) }
</script>

<template>
  <div ref="root">
    <Button
      variant="secondary"
      aria-haspopup="menu"
      :aria-label="`Change status of ${name}`"
      :aria-controls="expanded ? id : undefined"
      :aria-expanded="expanded ? 'true' : 'false'"
      :pending="pending"
      pending-label="Changing…"
      @click="menu?.toggle($event)"
      >Change status</Button
    >
    <Menu
      :id="id"
      ref="menu"
      :model="items"
      popup
      :aria-label="`Change status of ${name}`"
      :pt="pt"
      @show="expanded = true"
      @hide="expanded = false"
    />
  </div>
</template>
