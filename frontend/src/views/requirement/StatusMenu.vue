<script setup lang="ts">
// A requirement's status menu (DL-148): any status but its own and Approved, which comes only by
// hand (S2-C20) or through a completed approval request; the server decides each change. One
// menu button named with the requirement ("Change status of ERP-RQ-7"), opening PrimeVue's Menu
// (UI-STY-3), its change pending on the button (UI-FRM-8). The menu isn't at the end of `<body>`,
// which is inert behind the side panel (a modal dialog): it's in a fixed layer whose corner is
// kept at the document's, since PrimeVue places a popup in document coordinates (with
// `append-to="self"` it lands off to the side, and the panel scrolling to it closes it).
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
const layerId = useId()
const layer = ref<HTMLElement>()
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
function toggle(event: Event) {
  layer.value!.style.top = `${-window.scrollY}px`
  layer.value!.style.left = `${-window.scrollX}px`
  menu.value?.toggle(event)
}
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
      @click="toggle"
      >Change status</Button
    >
    <!-- Esc closes the menu alone: uncancelled, it would also close a dialog around it (the side
         panel). PrimeVue's handler doesn't cancel it. -->
    <div :id="layerId" ref="layer" class="fixed z-(--z-popover)" @keydown.esc.prevent />
    <Menu
      :id="id"
      ref="menu"
      :model="items"
      popup
      :append-to="`#${layerId}`"
      :aria-label="`Change status of ${name}`"
      :pt="pt"
      @show="expanded = true"
      @hide="expanded = false"
    />
  </div>
</template>
