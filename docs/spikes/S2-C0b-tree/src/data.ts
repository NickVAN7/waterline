// One checklist of 500 requirements, three levels deep (20 × 4 × 5), or 2,000 with ?rows=2000
// (the ranked view's cap, DL-159), and a mock server.
export interface Item {
  id: number
  number: string
  title: string
  status: string
  children: Item[]
}

const STATUSES = ['draft', 'in_review', 'approved', 'rejected']

export function checklist(): Item[] {
  let next = 1
  const make = (title: string, children: Item[] = []): Item => {
    const id = next++
    return { id, number: `RQ-${id}`, title, status: STATUSES[id % 4], children }
  }
  const tops = new URLSearchParams(location.search).get('rows') === '2000' ? 80 : 20
  return Array.from({ length: tops }, (_, a) => {
    const top = make(`Area ${a + 1}`)
    top.children = Array.from({ length: 4 }, (_, b) => {
      const mid = make(`Area ${a + 1}.${b + 1} requirement`)
      mid.children = Array.from({ length: 5 }, (_, c) => make(`Detail ${a + 1}.${b + 1}.${c + 1}`))
      return mid
    })
    return top
  })
}

/** ?open=none starts with every branch closed. */
export const startOpen = new URLSearchParams(location.search).get('open') !== 'none'

export const denyMoves = new URLSearchParams(location.search).get('deny') === '1'

/** The server decides every move (UI-SVR-5); here it allows or refuses all of them. */
export const serverLog: string[] = []
export async function serverMove(id: number, targetId: number, mode: string): Promise<boolean> {
  await new Promise((r) => setTimeout(r, 30))
  serverLog.push(`${id} ${mode} ${targetId} -> ${denyMoves ? 'deny' : 'allow'}`)
  return !denyMoves
}

/** The siblings array holding `id`, and its index, in our own data. */
export function locate(items: Item[], id: number): [Item[], number] | null {
  const i = items.findIndex((x) => x.id === id)
  if (i >= 0) return [items, i]
  for (const x of items) {
    const found = locate(x.children, id)
    if (found) return found
  }
  return null
}

/** The visible order of ids, depth first, for comparing the screen with the data. */
export function order(items: Item[]): number[] {
  return items.flatMap((x) => [x.id, ...order(x.children)])
}
