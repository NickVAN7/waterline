<script setup lang="ts">
// The app shell (docs/ui-design-guide.md §4): the skip link, a sticky header ("Waterline", then
// the current org's name, which is the org menu, UI-SHL-4, DL-137; the user menu at the end),
// the sidebar (My work, then the project selector and the selected project's pages, or on an admin
// page that area's pages, UI-SHL-5, DL-137), and `main`. Below
// 40rem the header wraps and scrolls with the page (DL-98); below 48rem the sidebar is behind a
// "Menu" disclosure in the header. Signed out (the status and not-found pages), the header has
// only the app name and Sign in.
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import Alert from '@/components/Alert.vue'
import Icon from '@/components/Icon.vue'
import { useSignOut } from '@/composables/useSignOut'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'

import OrgMenu from './shell/OrgMenu.vue'
import ProjectPages from './shell/ProjectPages.vue'
import ProjectSelector from './shell/ProjectSelector.vue'
import SidebarLink from './shell/SidebarLink.vue'
import UserMenu from './shell/UserMenu.vue'
import OrgNav from '@/views/org/OrgNav.vue'
import WorkspaceNav from '@/views/workspace/WorkspaceNav.vue'

const store = useCurrentUserStore()
const nav = useCurrentOrgStore()
const route = useRoute()
const { signOut, failed, failures, status, dismiss: dismissAlert } = useSignOut()

const menuOpen = ref(false)
const userMenu = ref<InstanceType<typeof UserMenu>>()
watch(
  () => route.path,
  () => (menuOpen.value = false),
)

// Focus returns to the user menu's button, whose Sign out caused the alert.
const dismiss = () => dismissAlert(() => userMenu.value?.focus())
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <a
      href="#main"
      class="sr-only rounded-md bg-surface-raised px-4 py-2 focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-(--z-dialog)"
    >
      Skip to main content
    </a>
    <header
      class="z-(--z-header) flex min-h-(--header-height) flex-wrap items-center gap-x-4 gap-y-2 border-b border-border-subtle bg-surface px-4 py-2 sm:sticky sm:top-0 sm:flex-nowrap sm:py-0"
    >
      <button
        v-if="store.me"
        type="button"
        aria-controls="sidebar"
        :aria-expanded="menuOpen ? 'true' : 'false'"
        class="inline-flex min-h-(--control-height) items-center gap-2 rounded-md px-2 hover:bg-hover md:hidden"
        @click="menuOpen = !menuOpen"
      >
        <Icon name="menu" />Menu
      </button>
      <RouterLink to="/" class="text-lg font-semibold text-text no-underline">Waterline</RouterLink>
      <OrgMenu v-if="store.me" />
      <div class="flex-1" />
      <UserMenu v-if="store.me" ref="userMenu" @sign-out="signOut" />
      <RouterLink v-else :to="{ name: 'sign-in' }">Sign in</RouterLink>
    </header>
    <div class="flex flex-1 flex-col md:flex-row">
      <div
        v-if="store.me"
        id="sidebar"
        :class="[
          'w-full shrink-0 flex-col gap-4 border-r border-border-subtle bg-surface p-4 md:flex md:w-(--sidebar-width)',
          menuOpen ? 'flex' : 'hidden',
        ]"
      >
        <nav aria-label="Main" class="flex flex-col gap-4">
          <div class="border-b border-border-subtle pb-4 font-semibold">
            <SidebarLink to="/"><Icon name="home" />My work</SidebarLink>
          </div>
          <ProjectSelector v-if="!route.meta.adminArea" />
        </nav>
        <WorkspaceNav v-if="route.meta.adminArea === 'workspace'" />
        <!-- The URL's org only: on a slug the user doesn't see (the not-found page), none. -->
        <OrgNav
          v-else-if="
            route.meta.adminArea === 'org' && nav.org && nav.org.slug === route.params.orgSlug
          "
          :org="nav.org"
        />
        <ProjectPages
          v-else-if="!route.meta.adminArea && nav.project"
          :key="nav.project.id"
          :project="nav.project"
          :org-slug="nav.org?.slug"
        />
      </div>
      <main
        id="main"
        tabindex="-1"
        class="flex w-full max-w-(--content-wide) min-w-0 flex-1 flex-col gap-4 p-4 sm:p-6"
      >
        <Alert v-if="failed" :key="failures" tone="danger" live dismissible @dismiss="dismiss">
          {{ failed }}
        </Alert>
        <slot />
        <p class="sr-only" aria-live="polite">{{ status }}</p>
      </main>
    </div>
  </div>
</template>
