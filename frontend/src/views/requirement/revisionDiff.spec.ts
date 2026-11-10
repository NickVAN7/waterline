import { describe, expect, it } from 'vitest'

import { diffDescription, diffWords, shown } from './revisionDiff'

describe('revisionDiff (DL-145)', () => {
  it('marks a one-word edit inside a line as that word, removed then added', () => {
    expect(diffDescription('Intro\nPay in 30 days\n', 'Intro\nPay in 45 days\n')).toEqual([
      { kind: 'same', lines: ['Intro'] },
      {
        kind: 'changed',
        pieces: [
          { text: 'Pay in ', kind: 'same' },
          { text: '30', kind: 'removed' },
          { text: '45', kind: 'added' },
          { text: ' days', kind: 'same' },
        ],
      },
    ])
  })

  it('keeps an unchanged run as its lines, and an added or removed line whole', () => {
    expect(diffDescription('a\nb\nc\nd\ngone\n', 'a\nb\nc\nd\n')).toEqual([
      { kind: 'same', lines: ['a', 'b', 'c', 'd'] },
      { kind: 'changed', pieces: [{ text: 'gone', kind: 'removed' }] },
    ])
    expect(diffDescription('a\n', 'a\nnew line\n')).toEqual([
      { kind: 'same', lines: ['a'] },
      { kind: 'changed', pieces: [{ text: 'new line', kind: 'added' }] },
    ])
  })

  it('reads CRLF line ends as line ends', () => {
    expect(diffDescription('a\r\nb\r\n', 'a\r\nc\r\n')[0]).toEqual({ kind: 'same', lines: ['a'] })
  })

  it('names a change of whitespace alone, which would otherwise mark nothing', () => {
    // Two paragraphs merged: a removed blank line.
    const [, merged] = diffDescription('Intro\n\nPay in 30 days\n', 'Intro\nPay in 30 days\n')
    expect(merged).toEqual({ kind: 'changed', pieces: [{ text: '', kind: 'removed' }] })
    expect(shown({ text: '', kind: 'removed' })).toBe('(blank line)')
    // Only a final line break added: still marked.
    const [ending] = diffDescription('a', 'a\n')
    expect(ending).toEqual({
      kind: 'changed',
      pieces: [
        { text: 'a', kind: 'same' },
        { text: '\n', kind: 'added' },
      ],
    })
    expect(shown({ text: '\n', kind: 'added' })).toBe('(line break)')
    expect(shown({ text: ' ', kind: 'added' })).toBe('(space)')
    expect(shown({ text: ' ', kind: 'same' })).toBe(' ')
    expect(shown({ text: 'word ', kind: 'added' })).toBe('word ')
  })

  it('diffs a title word by word', () => {
    expect(diffWords('Ship the report', 'Ship the final report')).toEqual([
      { text: 'Ship the ', kind: 'same' },
      { text: 'final ', kind: 'added' },
      { text: 'report', kind: 'same' },
    ])
  })
})
