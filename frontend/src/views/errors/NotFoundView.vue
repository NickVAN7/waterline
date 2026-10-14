<template>
  <section class="flex max-w-(--content-narrow) flex-col gap-4">
    <p class="m-0 text-sm text-text-muted">Error 404</p>
    <h1 class="m-0 text-2xl leading-tight font-semibold">Page not found</h1>
    <p class="m-0">There's nothing at this address. It may have moved, or the link may be wrong.</p>
    <div class="flex flex-wrap items-center gap-4">
      <RouterLink to="/" class="font-medium">Go to My work</RouterLink>
      <RouterLink :to="{ name: 'status' }" class="text-sm">System status</RouterLink>
    </div>
  </section>
</template>
