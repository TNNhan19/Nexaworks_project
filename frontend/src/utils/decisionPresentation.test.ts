import { describe, expect, it } from 'vitest'
import { businessEvidence, businessReason, committedCustomerFact, decisionConclusion, decisionImpact, priorityLabel } from './decisionPresentation'

describe('decision presentation', () => {
  it('maps blocked decisions and dependency evidence without exposing codes as the conclusion', () => {
    expect(decisionConclusion('BLOCKED', 'en')).toBe('Cannot proceed yet')
    expect(decisionConclusion('BLOCKED', 'vi')).toBe('Chưa thể thực hiện')
    expect(decisionConclusion('BLOCKED', 'ja')).toBe('まだ実行できません')
    expect(businessReason('DEPENDENCY_NOT_SATISFIED', 'vi')).toContain('tiên quyết')
    expect(decisionImpact('DEPENDENCY_NOT_SATISFIED', ['W005'], 'vi')).toContain('W005')
  })

  it('uses friendly priority bands for normalized and percentage-like scores', () => {
    expect(priorityLabel(0.8462, 'vi')).toBe('Rất cao')
    expect(priorityLabel(84.62, 'en')).toBe('Very high')
    expect(priorityLabel(65, 'ja')).toBe('高い')
    expect(priorityLabel(45, 'vi')).toBe('Trung bình')
    expect(priorityLabel(20, 'en')).toBe('Low')
  })

  it('does not invent a business explanation or impact for unknown backend codes', () => {
    expect(businessReason('UNSEEN_BACKEND_REASON', 'en')).toBeNull()
    expect(decisionImpact('UNSEEN_BACKEND_REASON', ['W005'], 'en')).toBeNull()
  })

  it('keeps only business-facing facts and phrases committed delivery from backend facts', () => {
    expect(businessEvidence({ completion_date: '2035-04-01', base_required_hours: 40, planner_code: 'X' }, 'vi')).toEqual([
      { label: 'Ngày bàn giao dự kiến', value: '2035-04-01', fieldKey: 'completion_date' },
    ])
    expect(committedCustomerFact(true, 'C007', 'vi')).toBe('Đã có cam kết bàn giao cho khách hàng C007.')
    expect(committedCustomerFact(false, 'C007', 'vi')).toBeNull()
  })
})
