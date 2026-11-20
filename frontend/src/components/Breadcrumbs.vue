<script setup lang="ts">
// A page's breadcrumb trail, above its `h1` (DL-327): PrimeVue's `Breadcrumb` in
// `nav aria-label="Breadcrumb"` and an `ol`, its chevrons decorative. Every crumb but the last is
// a link; the last, the page itself, is plain text with `aria-current="page"`. An item's ID is
// mono; the org's crumb has a building icon. Under 40rem the middle crumbs fold into a "…" menu
// button ("Show 2 more levels") listing them as links, the first and last kept. Nothing renders
// for fewer than two crumbs: a top-level page shows none.
import Breadcrumb from 'primevue/breadcrumb'
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import { computed, nextTick, ref, useId } from 'vue'
import { type RouteLocationRaw, useRouter } from 'vue-router'

import Icon, { type IconName } from './Icon.vue'

export type Crumb = { label: string; to?: RouteLocationRaw; mono?: boolean; icon?: IconName }

const props = defineProps<{ crumbs: Crumb[] }>()

const router = useRouter()
const menuId = useId()
const menu = ref<InstanceType<typeof Menu>>()
const expanded = ref(false)
// The fold's menu is mounted at its first use: most pages are never narrow enough to need it.
const used = ref(false)
async function toggle(event: Event) {
  // Read now: `currentTarget` is gone once the event has been handled.
  const target = event.currentTarget as HTMLElement
  used.value = true
  await nextTick()
  menu.value?.toggle(event, target)
}

const FOLD = 'fold'
const middle = computed(() => props.crumbs.slice(1, -1))
// The fold's own item sits after the first crumb; each middle crumb is hidden under 40rem.
const model = computed<MenuItem[]>(() => {
  const [first, ...rest] = props.crumbs.map((crumb, index) => ({ ...crumb, key: `${index}` }))
  const last = rest.pop()
  return [
    first!,
    ...(middle.value.length ? [{ key: FOLD, label: '…', class: 'sm:hidden' }] : []),
    ...rest.map((crumb) => ({ ...crumb, class: 'max-sm:hidden' })),
    { ...last!, current: true },
  ]
})
const folded = computed<MenuItem[]>(() =>
  middle.value.map((crumb) => ({
    label: crumb.label,
    url: router.resolve(crumb.to!).href,
    // A link's href, for a new tab; a plain click navigates in the app.
    command: ({ originalEvent }) => {
      const event = originalEvent as MouseEvent
      if (event.ctrlKey || event.metaKey || event.shiftKey) return
      event.preventDefault()
      void router.push(crumb.to!)
    },
  })),
)
const levels = computed(() =>
  middle.value.length === 1 ? 'Show 1 more level' : `Show ${middle.value.length} more levels`,
)
// The chevrons are drawn in each crumb, so a folded crumb's goes with it.
// PrimeVue's own CSS keeps the trail on one line and scrolls it with the scrollbar hidden, so a
// trail wider than its room (beside the split pane, zoomed) would be cut off: it wraps instead.
const pt = {
  root: { class: 'overflow-visible' },
  list: { class: 'flex-wrap' },
  separator: { class: 'hidden' },
}
// PrimeVue sets `aria-level`, which a menu item may not have (axe `aria-allowed-attr`).
const menuPt = { item: () => ({ 'aria-level': undefined }) }
</script>

<template>
  <Breadcrumb
    v-if="crumbs.length > 1"
    :model="model"
    :pt="pt"
    aria-label="Breadcrumb"
    class="text-xs"
  >
    <template #item="{ item }">
      <span class="flex items-center gap-1">
        <Icon v-if="item.key !== '0'" name="chevron-right" class="text-text-muted" />
        <template v-if="item.key === FOLD">
          <button
            type="button"
            aria-haspopup="menu"
            :aria-controls="expanded ? menuId : undefined"
            :aria-expanded="expanded ? 'true' : 'false'"
            :aria-label="levels"
            :title="levels"
            class="inline-flex min-h-(--target-min) min-w-(--target-min) items-center justify-center rounded-md text-text-muted hover:bg-hover hover:text-text"
            @click="toggle"
          >
            …
          </button>
          <Menu
            v-if="used"
            :id="menuId"
            ref="menu"
            :model="folded"
            popup
            :aria-label="levels"
            :pt="menuPt"
            @show="expanded = true"
            @hide="expanded = false"
          />
        </template>
        <span
          v-else-if="item.current"
          aria-current="page"
          :class="['flex items-center gap-1 text-text', item.mono && 'font-mono']"
          ><Icon v-if="item.icon" :name="item.icon as IconName" />{{ item.label }}</span
        >
        <!-- Only the last crumb is the page: a link to the page it's on (Workspace, on Staff) would
             otherwise get RouterLink's own `aria-current="page"`. -->
        <RouterLink
          v-else
          :to="item.to"
          aria-current="false"
          :class="[
            'flex items-center gap-1 text-text-muted no-underline hover:text-text hover:underline focus-visible:text-text focus-visible:underline',
            item.mono && 'font-mono',
          ]"
          ><Icon v-if="item.icon" :name="item.icon as IconName" />{{ item.label }}</RouterLink
        >
      </span>
    </template>
  </Breadcrumb>
</template>
