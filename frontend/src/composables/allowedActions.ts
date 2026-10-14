/**
 * The `allowed_actions` pattern (build plan, "Allowed actions"): a screen shows an action only when
 * the entity's `allowed_actions` lists it. A hint only; the server re-checks every request.
 */
import type { components } from '@/api/schema'

export type Action = components['schemas']['Action']

export function allows(entity: { allowed_actions: Action[] } | null | undefined, action: Action) {
  return entity?.allowed_actions.includes(action) ?? false
}
