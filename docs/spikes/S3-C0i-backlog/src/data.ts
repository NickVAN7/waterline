// One backlog of 500 tasks, or 2,000 with ?rows=2000 (about the most a project's backlog shows,
// DL-159's cap), and a mock server that decides every move (UI-SVR-5).
export interface Task {
  id: number
  number: string
  title: string
  status: string
  assignee: string
}

const STATUSES = ['To do', 'In progress', 'In review', 'Done']
const PEOPLE = ['Ben Brooks', 'Finn Fischer', 'Sam Silva', 'Casey Cole', '']

export function backlog(): Task[] {
  const n = new URLSearchParams(location.search).get('rows') === '2000' ? 2000 : 500
  return Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    number: `TA-${i + 1}`,
    title: `Task ${i + 1}`,
    status: STATUSES[i % 4],
    assignee: PEOPLE[i % 5],
  }))
}

export const denyMoves = new URLSearchParams(location.search).get('deny') === '1'

/** The server allows or refuses every move; 30 ms, as a fast local API would take. */
export const serverLog: string[] = []
export async function serverMove(id: number, to: number): Promise<boolean> {
  await new Promise((r) => setTimeout(r, 30))
  serverLog.push(`${id} -> ${to} ${denyMoves ? 'deny' : 'allow'}`)
  return !denyMoves
}

/** Moves `id` to index `to` in place. */
export function moveTo(items: Task[], id: number, to: number): void {
  const from = items.findIndex((t) => t.id === id)
  const [moved] = items.splice(from, 1)
  items.splice(to, 0, moved)
}

export type Direction = 'top' | 'up' | 'down' | 'bottom'
/** The index a menu move takes the task at `from` to, or null at the end it can't pass. */
export function target(from: number, length: number, dir: Direction): number | null {
  const to = { top: 0, up: from - 1, down: from + 1, bottom: length - 1 }[dir]
  return to < 0 || to >= length || to === from ? null : to
}

export const MESSAGE = 'The server refused the move; the backlog is unchanged.'
