/**
 * A new requirement's description, by the project's type (design-doc §6, "Acceptance criteria
 * live in the description"; DL-149): headings and an empty numbered list, never checkboxes or
 * placeholder comments. The server injects nothing; changing a project's type changes no
 * requirement.
 */
import type { components } from '@/api/schema'
import { PRIORITY } from '@/app/labels'

type ProjectType = components['schemas']['ProjectType']

const SOFTWARE = '## Context\n\n\n## Acceptance Criteria\n\n1. '
const ERP =
  '## Business Process\n\n\n## Current State\n\n\n## Future State\n\n\n## Acceptance Criteria\n\n1. '

export const DESCRIPTION_TEMPLATE: Record<ProjectType, string> = {
  software: SOFTWARE,
  general: SOFTWARE,
  erp: ERP,
}

type Priority = components['schemas']['Priority']

/** What the create form holds: carried to its full page in the history entry's state, so
 * expanding the dialog keeps what was typed (UI-SHL-12, UI-FRM-13). */
export interface RequirementDraft {
  title: string
  description_md: string
  priority: Priority
  parent_id: string
}

/** The draft in a history entry's state, or undefined when there's none or it isn't one. */
export function readDraft(state: unknown): RequirementDraft | undefined {
  const draft = (state as { draft?: Record<string, unknown> } | null)?.draft
  if (!draft) return undefined
  const { title, description_md, priority, parent_id } = draft
  if (
    typeof title !== 'string' ||
    typeof description_md !== 'string' ||
    typeof priority !== 'string' ||
    !Object.prototype.hasOwnProperty.call(PRIORITY, priority) ||
    typeof parent_id !== 'string'
  )
    return undefined
  return { title, description_md, priority: priority as Priority, parent_id }
}
