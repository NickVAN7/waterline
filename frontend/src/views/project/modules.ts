/** Module choice's shared rules (design-doc §1.1), for the create dialog and settings. */
import type { components } from '@/api/schema'

type ProjectType = components['schemas']['ProjectType']
type ProjectModule = components['schemas']['ProjectModule']

// The modules a project may enable (the API's `ProjectModule`); the rest of module guidance's are
// v2 and only described. Typed from the schema, so a new module is a compile error here.
const ENABLEABLE: Record<ProjectModule, true> = { sprints: true, github: true }

export const enableable = (module: string): module is ProjectModule => module in ENABLEABLE

/** The type's recommended modules that may be enabled: what the server would seed. */
export function recommendedFor(
  guidance: components['schemas']['ModuleGuidance'] | null,
  type: ProjectType,
): ProjectModule[] {
  return (guidance?.types.find((t) => t.type === type)?.recommended ?? []).filter(enableable)
}
