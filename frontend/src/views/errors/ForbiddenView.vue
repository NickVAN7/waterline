<script setup lang="ts">
// A page whose existence is public but which this person may not use, such as an admin page
// (UI-FBK-14, §6.1): inside the shell, with an "Error 403" label, an `h1`, one sentence saying
// who to ask, a link to My work, and a quieter one to system status.
defineProps<{ whoToAsk: string }>()
</script>

<template>
  <section class="flex max-w-(--content-narrow) flex-col gap-4">
    <p class="m-0 text-sm text-text-muted">Error 403</p>
    <h1 class="m-0 text-2xl leading-tight font-semibold">You can't open this page</h1>
    <p class="m-0">{{ whoToAsk }}</p>
    <div class="flex flex-wrap items-center gap-4">
      <RouterLink to="/" class="font-medium">Go to My work</RouterLink>
      <RouterLink :to="{ name: 'status' }" class="text-sm">System status</RouterLink>
    </div>
  </section>
</template>
