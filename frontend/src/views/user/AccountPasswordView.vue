<script setup lang="ts">
// Change password (`/account/password`; design-doc §4, DL-137): its own page, reached from account
// settings. The forced change is `ChangePasswordView`, on the auth card.
import PageHeader from '@/components/PageHeader.vue'
import ChangePasswordForm from '@/views/auth/ChangePasswordForm.vue'
</script>

<template>
  <div class="flex max-w-(--content-narrow) flex-col gap-6">
    <PageHeader title="Change password" />
    <p class="m-0 text-text-muted">Changing it signs you out everywhere else.</p>
    <ChangePasswordForm />
    <RouterLink :to="{ name: 'account' }" class="self-start text-sm"
      >Back to account settings</RouterLink
    >
  </div>
</template>
