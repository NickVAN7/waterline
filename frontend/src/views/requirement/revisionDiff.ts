/**
 * The revision compare's diff (design-doc §6.1, DL-145, UI-MD-3), on the raw markdown, never the
 * rendered HTML: line by line, then word by word inside a changed run (a removed run followed by
 * an added one), so a one-word edit shows as that word. Unchanged runs keep their lines, for
 * the view to collapse those over `SHOWN_UNCHANGED`.
 */
import { diffLines, diffWordsWithSpace, type Change } from 'diff'

export type Piece = { text: string; kind: 'same' | 'added' | 'removed' }
export type Block = { kind: 'same'; lines: string[] } | { kind: 'changed'; pieces: Piece[] }

/** An unchanged run longer than this collapses behind "Show N unchanged lines". */
export const SHOWN_UNCHANGED = 3

const piece = (change: Change): Piece => ({
  text: change.value,
  kind: change.added ? 'added' : change.removed ? 'removed' : 'same',
})

// One trailing line break off: each block is its own element, so it would draw an empty line.
const trimEnd = (text: string) => text.replace(/\r?\n$/, '')

/** What an added or removed piece shows: whitespace alone would mark nothing (a removed blank
 * line, a line break), so it's named. */
export function shown(piece: Piece): string {
  if (piece.kind === 'same' || piece.text.trim()) return piece.text
  if (!piece.text) return '(blank line)'
  return piece.text.includes('\n') ? '(line break)' : '(space)'
}

/** Word by word, for the title and inside a changed run. */
export function diffWords(older: string, newer: string): Piece[] {
  return diffWordsWithSpace(older, newer).map(piece)
}

export function diffDescription(older: string, newer: string): Block[] {
  const changes = diffLines(older, newer)
  const blocks: Block[] = []
  for (let i = 0; i < changes.length; i += 1) {
    const change = changes[i]!
    const next = changes[i + 1]
    if (!change.added && !change.removed) {
      blocks.push({ kind: 'same', lines: trimEnd(change.value).split(/\r?\n/) })
    } else if (change.removed && next?.added) {
      const pieces = diffWords(trimEnd(change.value), trimEnd(next.value))
      // Only a final line break changed: trimmed, the words match, so diff the untrimmed text.
      const marked = pieces.some((p) => p.kind !== 'same')
      blocks.push({
        kind: 'changed',
        pieces: marked ? pieces : diffWords(change.value, next.value),
      })
      i += 1
    } else {
      blocks.push({ kind: 'changed', pieces: [{ ...piece(change), text: trimEnd(change.value) }] })
    }
  }
  return blocks
}
