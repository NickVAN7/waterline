<script setup lang="ts">
// My work, the home page after sign-in (design-doc §11). Its projects section comes in S1-C14a.
import EmptyState from '@/components/EmptyState.vue'
</script>

<template>
  <div class="flex flex-col gap-6">
    <h1 class="m-0 text-2xl leading-tight font-semibold">My work</h1>
    <EmptyState heading="Nothing here yet">Projects you can open will appear here.</EmptyState>
  </div>
</template>
