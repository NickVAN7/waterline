/** Project settings' gate: who sees Settings in the project pages nav and the page itself. */
import { allows } from '@/composables/allowedActions'
import type { Project } from '@/stores/currentOrg'

/** Who a user without any settings action should ask (the 403 page, UI-FBK-14). */
export const WHO_TO_ASK =
  "Project settings are for the project's admins. Ask one of them if you need a change."

/** Any of the actions the settings page offers: its details, classification, or archiving. */
export function hasSettings(project: Project | null | undefined): boolean {
  return (
    allows(project, 'project.update') ||
    allows(project, 'project.raise_classification') ||
    allows(project, 'project.archive') ||
    allows(project, 'project.unarchive')
  )
}
