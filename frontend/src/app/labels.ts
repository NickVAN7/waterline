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
