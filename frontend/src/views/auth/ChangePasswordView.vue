<script setup lang="ts">
// The forced password change (build plan, "Authentication"): while `must_change_password` is set,
// the route guard sends every page here until a new password is chosen.
import { useRouter } from 'vue-router'

import ChangePasswordForm from './ChangePasswordForm.vue'

const router = useRouter()
</script>

<template>
  <h1 class="m-0 text-xl leading-tight font-semibold">Change your password</h1>
  <p class="m-0">Your password was set by an administrator. Choose a new one to continue.</p>
  <ChangePasswordForm with-sign-out @changed="router.replace('/')" />
</template>
