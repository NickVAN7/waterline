<script setup lang="ts">
// An item's ⋯ More actions menu (DL-325): one icon button named with the item ("More actions for
// ERP-RQ-7", its tooltip the native `title`, as `RowActions`), opening PrimeVue's Menu
// (UI-STY-3). Only the actions given are listed, so the caller passes those `allowed_actions`
// allow; nothing is rendered without any (hidden, not disabled). A `danger` action comes after a
// separator, in the danger color. The menu is in a fixed layer, as `StatusMenu`'s, so it works
// inside the side panel's modal dialog.
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import { computed, ref, useId } from 'vue'

import Icon from './Icon.vue'

export type MoreAction = { label: string; run: () => void; danger?: boolean }

const props = defineProps<{ name: string; actions: MoreAction[] }>()

const id = useId()
const layerId = useId()
const layer = ref<HTMLElement>()
const menu = ref<InstanceType<typeof Menu>>()
const button = ref<HTMLButtonElement>()
const expanded = ref(false)
defineExpose({ focus: () => button.value?.focus() })

const items = computed<MenuItem[]>(() =>
  props.actions.flatMap((action, index) => {
    const item: MenuItem = {
      label: action.label,
      danger: action.danger,
      // Focus goes back to the button first: the menu item that has it is about to go, and a
      // dialog the action opens returns focus to whatever had it (UI-FRM-14).
      command: () => {
        button.value?.focus()
        action.run()
      },
    }
    return action.danger && index > 0 ? [{ separator: true }, item] : [item]
  }),
)
function toggle(event: Event) {
  layer.value!.style.top = `${-window.scrollY}px`
  layer.value!.style.left = `${-window.scrollX}px`
  menu.value?.toggle(event)
}
// PrimeVue sets `aria-level`, which a menu item may not have (axe `aria-allowed-attr`).
const pt = {
  item: () => ({ 'aria-level': undefined }),
  itemContent: ({ context }: { context: { item: MenuItem } }) => ({
    class: context.item.danger ? 'text-danger' : undefined,
  }),
}
</script>

<template>
  <template v-if="actions.length">
    <button
      ref="button"
      type="button"
      aria-haspopup="menu"
      :aria-controls="expanded ? id : undefined"
      :aria-expanded="expanded ? 'true' : 'false'"
      :aria-label="`More actions for ${name}`"
      title="More actions"
      class="inline-flex size-(--control-height) items-center justify-center rounded-md border border-border text-text hover:bg-hover"
      @click="toggle"
    >
      <Icon name="more" />
    </button>
    <!-- Esc closes the menu alone, as `StatusMenu`'s: uncancelled, it would close the panel too. -->
    <div :id="layerId" ref="layer" class="fixed z-(--z-popover)" @keydown.esc.prevent />
    <Menu
      :id="id"
      ref="menu"
      :model="items"
      popup
      :append-to="`#${layerId}`"
      :aria-label="`More actions for ${name}`"
      :pt="pt"
      @show="expanded = true"
      @hide="expanded = false"
    />
  </template>
</template>
