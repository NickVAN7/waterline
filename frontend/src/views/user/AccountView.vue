<script setup lang="ts">
// Account settings (design-doc §4): your profile and your password.
import PageHeader from '@/components/PageHeader.vue'
import ChangePasswordForm from '@/views/auth/ChangePasswordForm.vue'

import ProfileForm from './ProfileForm.vue'
</script>

<template>
  <div class="flex max-w-(--content-narrow) flex-col gap-8">
    <PageHeader title="Account settings" />
    <section aria-labelledby="profile-heading" class="flex flex-col gap-4">
      <h2 id="profile-heading" class="m-0 text-lg font-semibold">Profile</h2>
      <ProfileForm />
    </section>
    <section aria-labelledby="password-heading" class="flex flex-col gap-4">
      <h2 id="password-heading" class="m-0 text-lg font-semibold">Password</h2>
      <p class="m-0 text-text-muted">Changing it signs you out everywhere else.</p>
      <ChangePasswordForm secondary />
    </section>
  </div>
</template>
