/**
 * The workspace the signed-in user administers, from `/me` (its `allowed_actions`, DL-45): the one
 * workspace there is (design-doc §4, "One workspace"), or null for someone who isn't its staff and
 * isn't a system admin, who then sees the workspace pages as not found.
 */
import { computed } from 'vue'

import { useCurrentUserStore } from '@/stores/currentUser'

export function useWorkspace() {
  const store = useCurrentUserStore()
  return computed(() => store.me?.workspaces[0] ?? null)
}
