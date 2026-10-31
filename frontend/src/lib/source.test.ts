import { describe, expect, it } from 'vitest'
import { looksLikeUrl } from './source'

describe('looksLikeUrl', () => {
  it('detects web links', () => {
    expect(looksLikeUrl('https://github.com/octocat/Hello-World')).toBe(true)
    expect(looksLikeUrl('  http://example.com/x')).toBe(true)
    expect(looksLikeUrl('github.com/octocat/Hello-World')).toBe(true)
  })
  it('treats filesystem paths as paths', () => {
    expect(looksLikeUrl('C:\\Users\\me\\repo')).toBe(false)
    expect(looksLikeUrl('/home/me/repo')).toBe(false)
    expect(looksLikeUrl('~/code/github.com/x')).toBe(false)
    expect(looksLikeUrl('')).toBe(false)
  })
})
