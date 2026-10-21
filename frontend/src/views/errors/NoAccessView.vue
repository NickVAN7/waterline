<script setup lang="ts">
// A signed-in user with no memberships left (design-doc §4, "Sessions"): nothing to open until an
// administrator adds them. Account settings still open.
import { ref } from 'vue'

import Alert from '@/components/Alert.vue'
import Button from '@/components/Button.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useSignOut } from '@/composables/useSignOut'
import { useCurrentUserStore } from '@/stores/currentUser'

const store = useCurrentUserStore()
const { signOut, pending, failed, failures, status, dismiss: dismissAlert } = useSignOut()
const signOutButton = ref<InstanceType<typeof Button>>()

// Focus returns to Sign out, which caused the alert.
const dismiss = () =>
  dismissAlert(() => (signOutButton.value?.$el as HTMLElement | undefined)?.focus())
</script>

<template>
  <PageHeader title="No access" />
  <p class="m-0">
    You're signed in as {{ store.me?.user.email }}, but you aren't a member of any organization or
    project yet. Ask an administrator to add you.
  </p>
  <Alert v-if="failed" :key="failures" tone="danger" live dismissible @dismiss="dismiss">{{
    failed
  }}</Alert>
  <div class="flex flex-wrap items-center gap-4">
    <Button
      ref="signOutButton"
      variant="secondary"
      :pending="pending"
      pending-label="Signing out…"
      @click="signOut"
      >Sign out</Button
    >
    <RouterLink :to="{ name: 'account' }">Account settings</RouterLink>
  </div>
  <p class="sr-only" aria-live="polite">{{ status }}</p>
</template>
