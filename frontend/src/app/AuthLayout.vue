<script setup lang="ts">
// The frame for sign-in and the forced password change (docs/ui-design-guide.md §4): a centered
// card, no navigation, still one `main` landmark.
</script>

<template>
  <main
    id="main"
    tabindex="-1"
    class="flex min-h-screen items-center justify-center bg-surface p-4"
  >
    <div
      class="flex w-full max-w-(--content-narrow) flex-col gap-6 rounded-lg border border-border-subtle bg-surface-raised p-6 sm:p-8"
    >
      <p class="m-0 text-lg font-semibold">Waterline</p>
      <slot />
    </div>
  </main>
</template>
