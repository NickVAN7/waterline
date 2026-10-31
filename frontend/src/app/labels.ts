/** Display labels for stored values (`frontend/CLAUDE.md`): the one place their words live. */
import type { components } from '@/api/schema'
import type { IconName } from '@/components/Icon.vue'

type ProjectStatus = components['schemas']['ProjectStatus']
type ProjectType = components['schemas']['ProjectType']
type RestrictionLevel = components['schemas']['RestrictionLevel']
type RestrictionCategory = components['schemas']['RestrictionCategory']
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

/** Project types (design-doc §1.1): the type seeds the modules and picks the labels. */
export const PROJECT_TYPE: Record<ProjectType, string> = {
  software: 'Software',
  erp: 'ERP implementation',
  general: 'General',
}

/** Module names (design-doc §1.1), v2 ones included: module guidance lists them all. */
export const MODULE: Record<string, string> = {
  sprints: 'Sprints',
  github: 'GitHub',
  raid: 'RAID log',
  status_reports: 'Status reports',
  budget: 'Budget',
  data_migration: 'Data migration',
  cutover: 'Cutover',
}

/** A module whose slice hasn't shipped, which can't be enabled (design-doc §1.1, DL-136). */
export const NOT_AVAILABLE_YET = 'Not available yet'

/** Restriction levels with the description shown beside each choice (design-doc §3.1, its
 * "Means" column), and the header badge's tone and icon (UI-FBK-6). */
export const RESTRICTION_LEVEL: Record<
  RestrictionLevel,
  BadgeLabel & { tone: 'info' | 'warning'; description: string }
> = {
  internal: {
    label: 'Internal',
    description:
      "For the firm and the client's project team; not for the public. Disclosure is embarrassing, not damaging.",
    tone: 'info',
    icon: 'info',
  },
  confidential: {
    label: 'Confidential',
    description:
      'Disclosure outside the project team would harm the client or the firm, or break a confidentiality agreement.',
    tone: 'warning',
    icon: 'warning',
  },
}

/** The null level's choice (design-doc §3.1): no badge. */
export const NO_RESTRICTION = {
  label: 'None',
  description: 'Not yet restricted; treated like Internal for every rule.',
}

/** The badge for categories with no level, in Internal's tone (UI-FBK-6). */
export const NO_RESTRICTION_LEVEL: BadgeLabel = {
  label: 'No restriction level',
  tone: RESTRICTION_LEVEL.internal.tone,
  icon: RESTRICTION_LEVEL.internal.icon,
}

/** Why content is sensitive (design-doc §3.1). */
export const RESTRICTION_CATEGORY: Record<RestrictionCategory, string> = {
  financial: 'Financial',
  proprietary: 'Proprietary',
  pii: 'Personal data (PII)',
  export_controlled: 'Export-controlled',
}

/** A project with no lead is flagged (UI-SHL-6). */
export const NO_LEAD: BadgeLabel = { label: 'No lead', tone: 'warning', icon: 'warning' }

/** The archived project's banner (UI-FBK-6): not dismissible, it says what the page is. */
export const ARCHIVED_BANNER = 'This project is archived. It is read-only.'

type WorkspaceRole = components['schemas']['WorkspaceRole']
type OrgRole = components['schemas']['OrgRole']
type ProjectRole = components['schemas']['ProjectRole']
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

/** Project roles, highest first (design-doc §5). */
export const PROJECT_ROLE: Record<ProjectRole, string> = {
  admin: 'Admin',
  member: 'Member',
  viewer: 'Viewer',
}

/** The user's own access to a project in a list (DL-153): their role, or admin by inheritance. */
export const MY_ACCESS: Record<components['schemas']['ProjectItem']['my_access'], string> = {
  ...PROJECT_ROLE,
  inherited_admin: 'Admin (inherited)',
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

/** An active account's status, and someone with no workspace role, in the users list's Status
 * and Role columns (DL-137, DL-183); the access review's no-role text. */
export const ACTIVE = 'Active'
export const USER = 'User'
export const NO_ROLE = 'None'

/** A per-person access review's Access cell on a project that isn't export-controlled, read by
 * screen readers only (DL-184). */
export const NOT_EXPORT_CONTROLLED = 'Not export-controlled'

/** The badge after a deactivated user's name, everywhere it appears (UI-FBK-6). */
export const DEACTIVATED: BadgeLabel = { label: 'Deactivated', tone: 'neutral', icon: 'x' }

/** A person's workspace role and system admin as text ("Owner, System admin"), or `none` with
 * neither: the users list's Role ("User") and the access review's ("None") (DL-188, DL-189). */
export function workspaceRoleText(
  role: WorkspaceRole | null | undefined,
  isSystemAdmin: boolean,
  none: string,
): string {
  const parts = [role && WORKSPACE_ROLE[role], isSystemAdmin && ACCESS_REASON.system_admin]
  return parts.filter(Boolean).join(', ') || none
}

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

/** A project key's problems (design-doc §3: 3–6 uppercase letters or digits, starting with a
 * letter): the identifier rule's, with the key's own characters. */
export const KEY_PROBLEM: Record<string, string> = {
  ...IDENTIFIER_PROBLEM,
  invalid_characters: 'may use only letters and digits',
}
