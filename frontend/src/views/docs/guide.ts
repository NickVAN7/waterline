// The reader's guide (DL-335, DL-337): one markdown file per page under `docs/user-guide/`,
// bundled at build time, each with front matter (`title`, `group`, `order`, `description`). The
// compose `web` service mounts the folder at the same relative path (DL-308).
const FILES = import.meta.glob('../../../../docs/user-guide/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

// Its local images, by the path a page names them with (`images/<file>`, DL-341).
const IMAGE_FILES = import.meta.glob('../../../../docs/user-guide/images/*', {
  query: '?url',
  import: 'default',
  eager: true,
}) as Record<string, string>

export const IMAGES: Record<string, string> = Object.fromEntries(
  Object.entries(IMAGE_FILES).map(([path, url]) => [`images/${path.split('/').pop()}`, url]),
)

export type GuidePage = {
  slug: string
  title: string
  group: string
  order: number
  description: string
  body: string
}

// The groups, in the sidebar's order, and Administration's note (DL-337).
export const GROUPS = ['Get started', 'Using Waterline', 'Administration', 'Reference'] as const
export const GROUP_NOTES: Partial<Record<string, string>> = {
  Administration: 'For workspace and organization owners and admins.',
}

/** A page from its file: the front matter's `key: value` lines, then the body. Throws on a
 * missing field or an unknown group, so a broken page fails the build's tests, not a reader. */
export function parsePage(slug: string, source: string): GuidePage {
  const match = /^---\n([\s\S]*?)\n---\n/.exec(source)
  if (!match) throw new Error(`${slug}: no front matter`)
  const fields: Record<string, string> = Object.fromEntries(
    match[1]!.split('\n').map((line) => {
      const at = line.indexOf(':')
      return [line.slice(0, at).trim(), line.slice(at + 1).trim()]
    }),
  )
  for (const key of ['title', 'group', 'order', 'description']) {
    if (!fields[key]) throw new Error(`${slug}: no ${key}`)
  }
  if (!(GROUPS as readonly string[]).includes(fields.group!)) {
    throw new Error(`${slug}: unknown group ${fields.group}`)
  }
  return {
    slug,
    title: fields.title!,
    group: fields.group!,
    order: Number(fields.order),
    description: fields.description!,
    body: source.slice(match[0].length),
  }
}

/** Every page in nav order: by group, then `order`. */
export function orderPages(pages: GuidePage[]): GuidePage[] {
  const rank = (page: GuidePage) => (GROUPS as readonly string[]).indexOf(page.group)
  return [...pages].sort((a, b) => rank(a) - rank(b) || a.order - b.order)
}

export const PAGES: GuidePage[] = orderPages(
  Object.entries(FILES).map(([path, source]) =>
    parsePage(path.split('/').pop()!.replace(/\.md$/, ''), source),
  ),
)

// The landing page's Start here cards (DL-339).
export const START_HERE: { slug: string; title: string; icon: 'home' | 'building' | 'check' }[] = [
  { slug: 'welcome', title: 'Welcome to Waterline', icon: 'home' },
  { slug: 'working-with-projects', title: 'Set up a project', icon: 'building' },
  { slug: 'approvals', title: 'Review and approve', icon: 'check' },
]
