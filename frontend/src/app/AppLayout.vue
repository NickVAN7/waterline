<script setup lang="ts">
// The frame around every screen: header, navigation, and the content area.
</script>

<template>
  <div class="layout">
    <header class="layout__header">
      <RouterLink to="/" class="layout__brand">Waterline</RouterLink>
      <nav class="layout__nav" aria-label="Main">
        <RouterLink to="/">Home</RouterLink>
      </nav>
    </header>
    <main class="layout__content">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.layout__header {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.layout__brand {
  font-weight: 600;
  font-size: 1.125rem;
  color: var(--color-text);
  text-decoration: none;
}

.layout__nav {
  display: flex;
  gap: 1rem;
}

.layout__content {
  flex: 1;
  width: 100%;
  max-width: 72rem;
  margin: 0 auto;
  padding: 1.5rem;
}
</style>
