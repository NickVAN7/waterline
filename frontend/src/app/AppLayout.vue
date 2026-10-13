<script setup lang="ts">
// The frame around signed-in screens until S1-C14a's shell replaces it: a header with the app
// name, My work, and sign-in or sign-out, and the content area.
import { useRouter } from 'vue-router'

import Button from '@/components/Button.vue'
import { useCurrentUserStore } from '@/stores/currentUser'

const store = useCurrentUserStore()
const router = useRouter()

async function signOut() {
  await store.signOut()
  await router.push({ name: 'sign-in' })
}
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <header
      class="flex min-h-(--header-height) flex-wrap items-center gap-6 border-b border-border-subtle bg-surface px-4"
    >
      <RouterLink to="/" class="text-lg font-semibold text-text no-underline">Waterline</RouterLink>
      <!-- No empty navigation landmark while signed out: a plain spacer keeps the layout. -->
      <nav v-if="store.me" aria-label="Main" class="flex flex-1 gap-4">
        <RouterLink to="/">My work</RouterLink>
      </nav>
      <div v-else class="flex-1" />
      <template v-if="store.me">
        <span class="text-sm text-text-muted">{{ store.me.user.name }}</span>
        <Button variant="secondary" @click="signOut">Sign out</Button>
      </template>
      <RouterLink v-else :to="{ name: 'sign-in' }">Sign in</RouterLink>
    </header>
    <main id="main" tabindex="-1" class="w-full max-w-(--content-wide) flex-1 p-4 sm:p-6">
      <slot />
    </main>
  </div>
</template>
