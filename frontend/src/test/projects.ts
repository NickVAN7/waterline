/** Projects as the API returns them, for component tests. */
import type { components } from '@/api/schema'
import type { Project } from '@/stores/currentOrg'

import { ACME } from './api'

type Item = components['schemas']['ProjectItem']

export function projectItem(key: string, overrides: Partial<Item> = {}): Item {
  return {
    id: `0190f0a0-0000-7000-8000-${key.padEnd(12, '0').slice(0, 12).toLowerCase()}`,
    key,
    name: `${key} project`,
    type: 'software',
    status: 'active',
    lead_id: null,
    organization_id: ACME.id,
    organization_slug: ACME.slug,
    ...overrides,
  }
}

export function project(overrides: Partial<Project> = {}): Project {
  return {
    id: '0190f0a0-0000-7000-8000-0000000000c1',
    organization_id: ACME.id,
    key: 'ERP',
    name: 'ERP rollout',
    description: null,
    type: 'erp',
    status: 'active',
    lead_id: '0190f0a0-0000-7000-8000-0000000000d1',
    lead_name: 'Liam Lead',
    lead_is_active: true,
    enabled_modules: [],
    archived: false,
    classification_level: null,
    classification_categories: [],
    modules_holding_data: [],
    allowed_actions: [],
    ...overrides,
  }
}
