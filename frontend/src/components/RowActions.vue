<script setup lang="ts">
// A table row's actions (UI-TBL-4): one menu button named with the row's identity ("Actions for
// Jane Doe"), opening PrimeVue's Menu (UI-STY-3). Only the actions given are listed: the caller
// passes those the row's `allowed_actions` allow. Nothing is rendered without any.
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import { computed, ref, useId } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

import Icon from './Icon.vue'

// An action runs `run`; a page to go to is a link (`to`), so it reads as navigation (UI-FRM-15).
export type RowAction = { label: string } & ({ run: () => void } | { to: RouteLocationRaw })

const props = defineProps<{ name: string; actions: RowAction[] }>()

const id = useId()
const menu = ref<InstanceType<typeof Menu>>()
const button = ref<HTMLButtonElement>()
const expanded = ref(false)
defineExpose({ focus: () => button.value?.focus() })

const items = computed<MenuItem[]>(() =>
  props.actions.map((action) =>
    'to' in action
      ? { label: action.label, route: action.to }
      : {
          label: action.label,
          // Focus goes back to this row's button first: the menu item that has it is about to go,
          // and a dialog the action opens returns focus to whatever had it (UI-FRM-14).
          command: () => {
            button.value?.focus()
            action.run()
          },
        },
  ),
)
// PrimeVue sets `aria-level`, which a menu item may not have (axe `aria-allowed-attr`).
const pt = { item: () => ({ 'aria-level': undefined }) }
</script>

<template>
  <template v-if="actions.length">
    <button
      ref="button"
      type="button"
      aria-haspopup="menu"
      :aria-controls="expanded ? id : undefined"
      :aria-expanded="expanded ? 'true' : 'false'"
      :aria-label="`Actions for ${name}`"
      :title="`Actions for ${name}`"
      class="inline-flex size-(--control-height-sm) items-center justify-center rounded-md text-text hover:bg-hover"
      @click="menu?.toggle($event)"
    >
      <Icon name="more" />
    </button>
    <Menu
      :id="id"
      ref="menu"
      :model="items"
      popup
      :aria-label="`Actions for ${name}`"
      :pt="pt"
      @show="expanded = true"
      @hide="expanded = false"
    >
      <template #item="{ item, props: itemProps }">
        <RouterLink v-if="item.route" v-slot="{ href, navigate }" :to="item.route" custom>
          <a :href="href" v-bind="itemProps.action" @click="navigate">{{ item.label }}</a>
        </RouterLink>
        <a v-else v-bind="itemProps.action">{{ item.label }}</a>
      </template>
    </Menu>
  </template>
</template>
