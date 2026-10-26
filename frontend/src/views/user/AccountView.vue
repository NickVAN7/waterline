<script setup lang="ts">
// Account settings (design-doc §4): your profile, the System / Light / Dark theme (UI-TOK-2,
// DL-164: applied as soon as it's chosen), and a link to change your password, its own page
// (DL-137).
import { computed } from 'vue'

import PageHeader from '@/components/PageHeader.vue'
import { type ThemeChoice, useTheme } from '@/composables/useTheme'

import ProfileForm from './ProfileForm.vue'

const { choice, choose } = useTheme()
const theme = computed({ get: () => choice.value, set: choose })

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: 'system', label: 'System (follows your device)' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]
</script>

<template>
  <div class="flex max-w-(--content-narrow) flex-col gap-8">
    <PageHeader title="Account settings" />
    <section aria-labelledby="profile-heading" class="flex flex-col gap-4">
      <h2 id="profile-heading" class="m-0 text-lg font-semibold">Profile</h2>
      <ProfileForm />
    </section>
    <section aria-labelledby="appearance-heading" class="flex flex-col gap-4">
      <h2 id="appearance-heading" class="m-0 text-lg font-semibold">Appearance</h2>
      <fieldset class="m-0 flex flex-col gap-2 border-0 p-0" aria-describedby="theme-note">
        <legend class="mb-2 p-0 font-medium">Theme</legend>
        <p id="theme-note" class="m-0 text-sm text-text-muted">Saved in this browser only.</p>
        <label v-for="option in THEMES" :key="option.value" class="flex items-center gap-2">
          <input
            v-model="theme"
            type="radio"
            name="theme"
            :value="option.value"
            class="size-(--target-min) shrink-0"
          />
          {{ option.label }}
        </label>
      </fieldset>
    </section>
    <section aria-labelledby="password-heading" class="flex flex-col gap-4">
      <h2 id="password-heading" class="m-0 text-lg font-semibold">Password</h2>
      <p class="m-0 text-text-muted">Changing it signs you out everywhere else.</p>
      <RouterLink :to="{ name: 'account-password' }" class="self-start font-medium"
        >Change password</RouterLink
      >
    </section>
  </div>
</template>
