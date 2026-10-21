/**
 * What a roster page (workspace staff; an org's members, S1-C15a; a project's members, S1-C16b)
 * gives the shared roster dialogs: its roles and its endpoints (build plan, "The workspace and org
 * API", "The org members API", "The project members API").
 * The rules are the server's (the roster, DL-59, DL-70); the dialogs only show what it answers.
 */
export type RoleOption = { value: string; label: string }

export type RosterPerson = { user_id: string; name: string; email: string; is_active: boolean }

export type NewPerson = {
  email: string
  username: string
  name: string
  password: string
  role: string
}

/** A project add's confirmations (DL-78, design-doc §3.1); the workspace and org rosters ignore them. */
export type AddOptions = { joinOrg: boolean; exportControlConfirmed: boolean }

export type Roster = {
  /** Where the person is added or removed, for the dialogs' words ("the workspace's staff"). */
  scope: string
  /**
   * Where their project memberships are, for the removal option ("the workspace's projects"); none
   * for a project's roster, which has no such option.
   */
  projects?: string
  /** An export-controlled project: every add confirms the person is authorized (design-doc §3.1). */
  exportControlled?: boolean
  roles: RoleOption[]
  /** The workspace whose user check the add-person form uses (DL-66). */
  workspaceId: string
  add: (email: string, role: string, options: AddOptions) => Promise<unknown>
  create: (person: NewPerson, options: AddOptions) => Promise<unknown>
  changeRole: (userId: string, role: string, newOwnerId?: string) => Promise<unknown>
  remove: (userId: string, withProjects: boolean, newOwnerId?: string) => Promise<unknown>
  /**
   * Everyone on the roster, for the replacement-owner picker (DL-59); none for a project's roster,
   * which has no last-owner guard (DL-71).
   */
  everyone?: () => Promise<RosterPerson[]>
}
