<script setup lang="ts">
// The non-drag way to move an item (UI-SVR-6, UI-TBL-5, DL-243): one menu button outside the
// widget, named with the item it moves ("Move PMT-RQ-7"), opening PrimeVue's Menu (UI-STY-3).
// A move its place rules out (Move up on the first) stays listed and focusable, `aria-disabled`
// in the disabled tokens with the reason in its label, so the keyboard reaches the reason too
// (PrimeVue skips a `disabled` item and fades it with opacity; UI-TOK-10). With nothing to move,
// the button is blocked with its reason beside it.
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import { computed, ref, useId } from 'vue'

import Button from './Button.vue'

export type MoveAction = { label: string; run: () => void; blockedReason?: string }

const props = defineProps<{
  // The item's identity, or null with nothing selected (`blockedReason` then says why).
  name: string | null
  actions: MoveAction[]
  blockedReason?: string
  pending?: boolean
}>()

const id = useId()
const reasonId = useId()
const menu = ref<InstanceType<typeof Menu>>()
const root = ref<HTMLElement>()
const expanded = ref(false)
defineExpose({ focus: () => root.value?.querySelector('button')?.focus() })

const blocked = computed(() => props.name === null)
const items = computed<MenuItem[]>(() =>
  props.actions.map((action) => ({
    label: action.blockedReason ? `${action.label} (${action.blockedReason})` : action.label,
    blocked: Boolean(action.blockedReason),
    // Focus goes back to the button first: the menu item that has it is about to go.
    command: () => {
      root.value?.querySelector('button')?.focus()
      if (!action.blockedReason) action.run()
    },
  })),
)
const label = computed(() => (props.name ? `Move ${props.name}` : 'Move'))
// PrimeVue sets `aria-level`, which a menu item may not have (axe `aria-allowed-attr`).
const pt = {
  item: ({ context }: { context: { item: MenuItem } }) => ({
    'aria-level': undefined,
    'aria-disabled': context.item.blocked ? 'true' : undefined,
  }),
  // On the content, which sets its own color over the item's.
  itemContent: ({ context }: { context: { item: MenuItem } }) => ({
    class: context.item.blocked ? 'text-disabled-text' : undefined,
  }),
}

function toggle(event: MouseEvent) {
  if (!blocked.value) menu.value?.toggle(event)
}
</script>

<template>
  <div ref="root" class="flex items-center gap-2">
    <Button
      variant="secondary"
      aria-haspopup="menu"
      :aria-controls="expanded ? id : undefined"
      :aria-expanded="expanded ? 'true' : 'false'"
      :aria-describedby="blocked ? reasonId : undefined"
      :blocked="blocked"
      :pending="pending"
      pending-label="Moving…"
      @click="toggle"
    >
      {{ label }}
    </Button>
    <span v-if="blocked" :id="reasonId" class="text-sm text-text-muted">{{ blockedReason }}</span>
    <Menu
      :id="id"
      ref="menu"
      :model="items"
      popup
      :aria-label="label"
      :pt="pt"
      @show="expanded = true"
      @hide="expanded = false"
    />
  </div>
</template>
