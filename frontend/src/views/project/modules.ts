/** Module choice's shared rules (design-doc §1.1), for the create dialog and settings. */
import type { components } from '@/api/schema'

type ProjectType = components['schemas']['ProjectType']
type ProjectModule = components['schemas']['ProjectModule']

// The modules the API's `ProjectModule` allows; the rest of module guidance's are v2. Typed from
// the schema, so a new module is a compile error here.
const ENABLEABLE: Record<ProjectModule, true> = { sprints: true, github: true }

export const enableable = (module: string): module is ProjectModule => module in ENABLEABLE

/** The type's recommended modules that may be enabled and have shipped: what the server would
 * seed (DL-136). */
export function recommendedFor(
  guidance: components['schemas']['ModuleGuidance'] | null,
  type: ProjectType,
): ProjectModule[] {
  const available = new Set(guidance?.modules.filter((m) => m.available).map((m) => m.module))
  return (guidance?.types.find((t) => t.type === type)?.recommended ?? []).filter(
    (m): m is ProjectModule => enableable(m) && available.has(m),
  )
}
