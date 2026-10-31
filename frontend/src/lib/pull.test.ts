import { describe, expect, it } from 'vitest'
import { parsePullNumber } from './pull'

describe('parsePullNumber', () => {
  it('accepts numbers, #numbers and pull links', () => {
    expect(parsePullNumber('42')).toBe(42)
    expect(parsePullNumber(' #42 ')).toBe(42)
    expect(parsePullNumber('https://github.com/octocat/Hello-World/pull/6')).toBe(6)
    expect(parsePullNumber('github.com/o/r/pull/12/files')).toBe(12)
  })
  it('rejects everything else', () => {
    for (const bad of ['', 'abc', '0', '-3', '1.5', '12abc', '999999999', '1; rm', 'https://evil.com/o/r/pull/3',
      'https://github.com/o/r/issues/3']) {
      expect(parsePullNumber(bad), bad).toBeNull()
    }
  })
})
