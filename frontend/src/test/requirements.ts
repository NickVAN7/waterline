/** Typed requirement fixtures for specs: a tree row and a full read (`frontend/CLAUDE.md`, Tests). */
import type { components } from '@/api/schema'

type Item = components['schemas']['RequirementItem']
type Requirement = components['schemas']['RequirementRead']

export const requirementId = (n: number) => `0190f0a0-0000-7000-8000-${String(n).padStart(12, '0')}`

/** A row of the tree: top level unless a parent's number is given. */
export function requirementItem(number: number, title: string, parent: number | null = null): Item {
  return {
    id: requirementId(number),
    number,
    parent_id: parent === null ? null : requirementId(parent),
    title,
    status: 'draft',
    priority: 'medium',
    restriction_level: null,
    restriction_categories: [],
    current_revision_id: null,
    approved_revision_id: null,
    awaiting_approval: false,
  }
}

/** A requirement as `POST`/`GET …/requirements/{number}` return it, just created. */
export function requirementRead(number: number, title: string): Requirement {
  return {
    ...requirementItem(number, title),
    description_md: '',
    reporter_id: 'u-ben',
    reporter_name: 'Ben',
    reporter_is_active: true,
    effective_restriction_level: null,
    effective_restriction_categories: [],
    approved_revision_number: null,
    has_children: false,
    ancestors: [],
    can_delete_children: false,
    approved_at: null,
    version: 1,
    created_at: '2026-11-02T12:00:00Z',
    updated_at: '2026-11-02T12:00:00Z',
    allowed_actions: [],
  }
}
