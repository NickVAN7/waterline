<script setup lang="ts">
// A requirement's status menu (DL-148, DL-388, DL-395): every status but Approved, which comes
// only by hand (S2-C20) or through a completed approval request, as the line below the list says;
// the current status is listed too, marked with a check and "(current)", `aria-disabled` and
// focusable, its command doing nothing (as `MoveToMenu`'s blocked items), in the text color, not
// the disabled tokens: it's where the requirement is, not a blocked choice (UI-TOK-10). The server
// decides each change. One menu button named with the requirement ("Change status of ERP-RQ-7"),
// opening PrimeVue's Menu (UI-STY-3), its change pending on the button (UI-FRM-8). The menu isn't
// at the end of `<body>`,
// which is inert behind the side panel (a modal dialog): it's in a fixed layer whose corner is
// kept at the document's, since PrimeVue places a popup in document coordinates (with
// `append-to="self"` it lands off to the side, and the panel scrolling to it closes it).
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import { computed, ref, useId } from 'vue'

import type { components } from '@/api/schema'
import { REQUIREMENT_STATUS } from '@/app/labels'
import Button from '@/components/Button.vue'
import Icon from '@/components/Icon.vue'

type Status = components['schemas']['RequirementStatus']

const props = defineProps<{ name: string; status: Status; pending?: boolean }>()
const emit = defineEmits<{ change: [status: Status] }>()

const id = useId()
const noteId = useId()
const layerId = useId()
const layer = ref<HTMLElement>()
const menu = ref<InstanceType<typeof Menu>>()
const root = ref<HTMLElement>()
const expanded = ref(false)
defineExpose({ focus: () => root.value?.querySelector('button')?.focus() })

const items = computed<MenuItem[]>(() =>
  (Object.keys(REQUIREMENT_STATUS) as Status[])
    .filter((status) => status === props.status || status !== 'approved')
    .map((status) => {
      const current = status === props.status
      return {
        label: `${REQUIREMENT_STATUS[status].label}${current ? ' (current)' : ''}`,
        current,
        // Focus goes back to the button first: the menu item that has it is about to go.
        command: () => {
          root.value?.querySelector('button')?.focus()
          if (!current) emit('change', status)
        },
      }
    }),
)
function toggle(event: Event) {
  layer.value!.style.top = `${-window.scrollY}px`
  layer.value!.style.left = `${-window.scrollX}px`
  menu.value?.toggle(event)
}
// PrimeVue sets `aria-level`, which a menu item may not have (axe `aria-allowed-attr`). The note
// sits outside the list (a menu holds only items), so the list is described by it.
const pt = {
  list: { 'aria-describedby': noteId },
  item: ({ context }: { context: { item: MenuItem } }) => ({
    'aria-level': undefined,
    'aria-disabled': context.item.current ? 'true' : undefined,
  }),
}
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
    >
      <!-- Every item holds the icon, hidden but the current one's, so the labels line up. -->
      <template #itemicon="{ item }">
        <Icon name="check" :class="item.current ? undefined : 'invisible'" />
      </template>
      <template #end>
        <p :id="noteId" class="m-0 max-w-60 px-3 py-2 text-sm text-text-muted">
          Approved is set by an approval.
        </p>
      </template>
    </Menu>
  </div>
</template>
