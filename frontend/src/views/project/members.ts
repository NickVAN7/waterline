/** A project's explicit members, every page: the lead picker's and the approver picker's list. */
import { api, client } from '@/api/client'
import type { components } from '@/api/schema'

type Member = components['schemas']['ProjectMemberRead']

export async function allMembers(projectKey: string): Promise<Member[]> {
  const found: Member[] = []
  for (;;) {
    const page = await api(
      client.GET('/api/projects/{key}/members', {
        params: { path: { key: projectKey }, query: { limit: 200, offset: found.length } },
      }),
    )
    found.push(...page.items)
    if (!page.items.length || found.length >= page.total) return found
  }
}
