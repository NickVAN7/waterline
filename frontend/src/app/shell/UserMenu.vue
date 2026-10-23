<script setup lang="ts">
// The user menu (UI-SHL-8, UI-TOK-2): account settings, the System / Light / Dark theme (radio
// items, so the choice is announced as checked), and sign out, with an icon in the danger tone.
// PrimeVue's Menu (UI-STY-3); its pass-through options give the theme items their radio role.
// "Workspace administration" leads to the workspace's admin pages for those who may see them
// (`workspace.view`; UI-SHL-10, DL-104), and "Organization administration" to the current org's
// (`org_member.manage`).
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import { computed, ref } from 'vue'

import Icon from '@/components/Icon.vue'
import { allows } from '@/composables/allowedActions'
import { type ThemeChoice, useTheme } from '@/composables/useTheme'
import { useWorkspace } from '@/composables/useWorkspace'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'

const emit = defineEmits<{ signOut: [] }>()

const store = useCurrentUserStore()
const { choice, choose } = useTheme()
const workspace = useWorkspace()
const nav = useCurrentOrgStore()

const menu = ref<InstanceType<typeof Menu>>()
const button = ref<HTMLButtonElement>()
defineExpose({ focus: () => button.value?.focus() })
const expanded = ref(false)

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: 'system', label: 'System theme' },
  { value: 'light', label: 'Light theme' },
  { value: 'dark', label: 'Dark theme' },
]

const items = computed<MenuItem[]>(() => [
  // A link, so it reads as navigation and opens in a new tab like any other (UI-FRM-15).
  { label: 'Account settings', route: { name: 'account' } },
  ...(allows(workspace.value, 'workspace.view')
    ? [{ label: 'Workspace administration', route: { name: 'workspace-staff' } }]
    : []),
  ...(nav.org && allows(nav.org, 'org_member.manage')
    ? [
        {
          label: 'Organization administration',
          route: { name: 'org-members', params: { orgSlug: nav.org.slug } },
        },
      ]
    : []),
  { separator: true },
  ...THEMES.map((theme) => ({
    label: theme.label,
    checked: choice.value === theme.value,
    command: () => choose(theme.value),
  })),
  { separator: true },
  // An icon and the danger tone set it apart (UI-SHL-4, DL-137).
  { label: 'Sign out', danger: true, command: () => emit('signOut') },
])

// Theme items are radio items: role and checked state on the item itself. PrimeVue also sets
// `aria-level`, which a menu item may not have (axe `aria-allowed-attr`), so it's dropped.
const pt = {
  item: ({ context }: { context: { item: MenuItem } }) => ({
    'aria-level': undefined,
    ...(context.item.checked === undefined
      ? {}
      : { role: 'menuitemradio', 'aria-checked': String(context.item.checked) }),
  }),
}
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
      <a v-else v-bind="itemProps.action">
        <Icon v-if="item.checked !== undefined" :name="item.checked ? 'check' : 'circle'" />
        {{ item.label }}
      </a>
    </template>
  </Menu>
</template>
