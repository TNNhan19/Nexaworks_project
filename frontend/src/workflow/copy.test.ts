import { describe, expect, it } from 'vitest'
import { workflowCopy } from './copy'

describe('workflow business copy', () => {
  it.each(['en', 'ja', 'vi'])('has complete staged-flow labels in %s', (language) => {
    const copy = workflowCopy(language)
    expect(copy.entry.title).toBeTruthy()
    expect(copy.planning.reviewWork).toBeTruthy()
    expect(copy.work.notAnalyzed).toBeTruthy()
    expect(copy.work.analyze).toBeTruthy()
    expect(copy.work.generate).toBeTruthy()
    expect(copy.gate.noDataTitle).toBeTruthy()
    expect(copy.validation.cash).toBeTruthy()
  })
  it('falls back safely to English for an unsupported locale', () => {
    expect(workflowCopy('fr').entry.title).toBe(workflowCopy('en').entry.title)
  })
  it('preserves the same work-first meaning in Japanese and Vietnamese', () => {
    expect(workflowCopy('ja').work.analysisExplain).toContain('実行順序')
    expect(workflowCopy('vi').work.analysisExplain).toContain('không phải thứ tự thực hiện')
  })
})
