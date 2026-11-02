/**
 * A new requirement's description, by the project's type (design-doc §6, "Acceptance criteria
 * live in the description"; DL-149): headings and an empty numbered list, never checkboxes or
 * placeholder comments. The server injects nothing; changing a project's type changes no
 * requirement.
 */
import type { components } from '@/api/schema'

type ProjectType = components['schemas']['ProjectType']

const SOFTWARE = '## Context\n\n\n## Acceptance Criteria\n\n1. '
const ERP =
  '## Business Process\n\n\n## Current State\n\n\n## Future State\n\n\n## Acceptance Criteria\n\n1. '

export const DESCRIPTION_TEMPLATE: Record<ProjectType, string> = {
  software: SOFTWARE,
  general: SOFTWARE,
  erp: ERP,
}
