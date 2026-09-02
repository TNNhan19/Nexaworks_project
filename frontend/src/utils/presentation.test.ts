import { describe, expect, it } from 'vitest'
import {
  decisionLabel,
  formatMoneyCompact,
  reasonLabel,
  statusLabel,
  uiLanguage,
} from './presentation'

describe('manager-facing presentation mappings', () => {
  it('keeps status meaning aligned across EN, JA, and VI', () => {
    expect(statusLabel('PLAN_AT_RISK', 'en')).toBe('Plan is at risk')
    expect(statusLabel('PLAN_AT_RISK', 'ja')).toBe('計画にリスクがあります')
    expect(statusLabel('PLAN_AT_RISK', 'vi')).toBe('Kế hoạch có rủi ro')
  })

  it('translates decisions into business actions', () => {
    expect(decisionLabel('NO_BID', 'en')).toBe('Do not pursue')
    expect(decisionLabel('NO_BID', 'ja')).toBe('参加しない')
    expect(decisionLabel('NO_BID', 'vi')).toBe('Không nên tham gia')
  })

  it('explains technical reasons while preserving a safe unknown-code fallback', () => {
    expect(reasonLabel('NO_BID_CAPACITY_CONSTRAINT', 'vi')).toContain('năng lực')
    expect(reasonLabel('USER_DEFERRED', 'en')).toContain('scenario')
    expect(reasonLabel('USER_DEFERRED', 'ja')).toContain('延期')
    expect(reasonLabel('USER_DEFERRED', 'vi')).toContain('kịch bản')
    expect(reasonLabel('ARBITRARY_NEW_REASON', 'en')).toBe('Arbitrary new reason')
  })

  it('supports regional language tags and compact JPY values', () => {
    expect(uiLanguage('ja-JP')).toBe('ja')
    expect(uiLanguage('vi-VN')).toBe('vi')
    expect(formatMoneyCompact(-700_000, 'en')).toBe('-¥700K')
    expect(formatMoneyCompact(18_000_000, 'en')).toBe('¥18M')
  })
})
