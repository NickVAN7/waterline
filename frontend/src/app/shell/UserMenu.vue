<script setup lang="ts">
// The user menu (UI-SHL-8): account settings, where the theme is chosen (UI-TOK-2, DL-164), and
// sign out, with an icon in the danger tone. PrimeVue's Menu (UI-STY-3).
// "Administration" leads to the workspace's admin pages for those who may see them
// (`workspace.view`; UI-SHL-10, DL-104); an org's are in the org menu (UI-SHL-4, DL-137).
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import { computed, ref } from 'vue'

import Icon from '@/components/Icon.vue'
import { allows } from '@/composables/allowedActions'
import { useWorkspace } from '@/composables/useWorkspace'
import { useCurrentUserStore } from '@/stores/currentUser'

const emit = defineEmits<{ signOut: [] }>()

const store = useCurrentUserStore()
const workspace = useWorkspace()

const menu = ref<InstanceType<typeof Menu>>()
const button = ref<HTMLButtonElement>()
defineExpose({ focus: () => button.value?.focus() })
const expanded = ref(false)

const items = computed<MenuItem[]>(() => [
  // A link, so it reads as navigation and opens in a new tab like any other (UI-FRM-15).
  { label: 'Account settings', route: { name: 'account' } },
  ...(allows(workspace.value, 'workspace.view')
    ? [{ label: 'Administration', route: { name: 'workspace-staff' } }]
    : []),
  { separator: true },
  // An icon and the danger tone set it apart (UI-SHL-4, DL-137).
  { label: 'Sign out', danger: true, command: () => emit('signOut') },
])

// PrimeVue sets `aria-level`, which a menu item may not have (axe `aria-allowed-attr`).
const pt = { item: { 'aria-level': undefined } }
</script>

<template>
  <button
    v-if="store.me"
    ref="button"
    type="button"
    aria-haspopup="menu"
    :aria-controls="expanded ? 'user-menu' : undefined"
    :aria-expanded="expanded ? 'true' : 'false'"
    class="inline-flex min-h-(--control-height) items-center gap-2 rounded-md px-3 text-text hover:bg-hover"
    @click="menu?.toggle($event)"
  >
    <span class="sr-only">Account menu: </span>{{ store.me.user.name }}
    <Icon name="chevron-down" />
  </button>
  <Menu
    id="user-menu"
    ref="menu"
    :model="items"
    popup
    aria-label="Account menu"
    :pt="pt"
    @show="expanded = true"
    @hide="expanded = false"
  >
    <template #item="{ item, props: itemProps }">
      <RouterLink v-if="item.route" v-slot="{ href, navigate }" :to="item.route" custom>
        <a :href="href" v-bind="itemProps.action" @click="navigate">{{ item.label }}</a>
      </RouterLink>
      <a v-else-if="item.danger" v-bind="itemProps.action">
        <!-- Our own content takes the tone: PrimeVue's colors are the preset's (UI-STY-2). -->
        <span class="inline-flex items-center gap-2 text-danger"
          ><Icon name="sign-out" />{{ item.label }}</span
        >
      </a>
    </template>
  </Menu>
</template>
