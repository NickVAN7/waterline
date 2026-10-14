/** Display labels for stored values (`frontend/CLAUDE.md`): the one place their words live. */
import type { components } from '@/api/schema'
import type { IconName } from '@/components/Icon.vue'

type ProjectStatus = components['schemas']['ProjectStatus']
export type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info'

export type BadgeLabel = { label: string; tone: Tone; icon: IconName }

/** A badge's text, tone, and icon, so the status never relies on color alone (UI-FBK-5; the
 * guide's mapping for project status). */
export const PROJECT_STATUS: Record<ProjectStatus, BadgeLabel> = {
  planning: { label: 'Planning', tone: 'neutral', icon: 'circle' },
  active: { label: 'Active', tone: 'success', icon: 'check' },
  on_hold: { label: 'On hold', tone: 'warning', icon: 'warning' },
  completed: { label: 'Completed', tone: 'info', icon: 'check' },
  cancelled: { label: 'Cancelled', tone: 'neutral', icon: 'x' },
}

/** A project with no lead is flagged (UI-SHL-6). */
export const NO_LEAD: BadgeLabel = { label: 'No lead', tone: 'warning', icon: 'warning' }

/** The archived project's banner (UI-FBK-6): not dismissible, it says what the page is. */
export const ARCHIVED_BANNER = 'This project is archived. It is read-only.'

type WorkspaceRole = components['schemas']['WorkspaceRole']
type OrgRole = components['schemas']['OrgRole']
type AccessReason = components['schemas']['AccessReason']
type AccessKind = components['schemas']['AccessKind']

/** Workspace staff roles, highest first (design-doc §4). */
export const WORKSPACE_ROLE: Record<WorkspaceRole, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
}

/** Org roles, highest first (design-doc §4). */
export const ORG_ROLE: Record<OrgRole, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
}

/** Why someone reaches an org or project, in an access review (design-doc §5, "Access review"). */
export const ACCESS_REASON: Record<AccessReason, string> = {
  system_admin: 'System admin',
  workspace_owner: 'Workspace owner',
  workspace_admin: 'Workspace admin',
  org_owner: 'Org owner',
  org_admin: 'Org admin',
  org_member: 'Org member',
  project_membership: 'A role on one of its projects',
  project_admin: 'Project admin',
  project_member: 'Project member',
  project_viewer: 'Project viewer',
}

/** What a person may do on a project (design-doc §3.1). */
export const ACCESS_KIND: Record<AccessKind, string> = {
  content: 'Content and management',
  management: 'Management only',
}

/** The badge after a deactivated user's name, everywhere it appears (UI-FBK-6). */
export const DEACTIVATED: BadgeLabel = { label: 'Deactivated', tone: 'neutral', icon: 'x' }

/** The badge on a system admin, read-only on the users page (design-doc §4). */
export const SYSTEM_ADMIN: BadgeLabel = { label: 'System admin', tone: 'info', icon: 'check' }

/** What a live availability check says about a slug or username (UI-FRM-9), after the field's
 * name: the identifier rule's problems (design-doc §3, §4) and `taken`. */
export const IDENTIFIER_PROBLEM: Record<string, string> = {
  taken: 'is taken',
  reserved: 'is reserved',
  too_short: 'is too short',
  too_long: 'is too long',
  must_start_with_letter: 'must start with a letter',
  invalid_characters: 'may use only lowercase letters, digits, and hyphens',
}
