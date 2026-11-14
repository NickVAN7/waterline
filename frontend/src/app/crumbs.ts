// The breadcrumb trails' first crumbs (DL-327): the workspace administration area (its first
// page), an org (its projects, with the building icon), and a project page's org and project.
import type { Crumb } from '@/components/Breadcrumbs.vue'
import { type Project, useCurrentOrgStore } from '@/stores/currentOrg'

export const WORKSPACE_CRUMB: Crumb = { label: 'Workspace', to: { name: 'workspace-staff' } }

export function orgCrumb(org: { name: string; slug: string }): Crumb {
  return {
    label: org.name,
    icon: 'building',
    to: { name: 'org-projects', params: { orgSlug: org.slug } },
  }
}

/** A project page's trail: its org (when the user's list holds it), the project (its home), then
 * the page's own crumbs, the last being the page; with none, the project is the page. */
export function projectCrumbs(project: Project, trail: Crumb[] = []): Crumb[] {
  const org = useCurrentOrgStore().orgs.find((o) => o.id === project.organization_id)
  return [
    ...(org ? [orgCrumb(org)] : []),
    { label: project.name, to: { name: 'project-home', params: { key: project.key } } },
    ...trail,
  ]
}
