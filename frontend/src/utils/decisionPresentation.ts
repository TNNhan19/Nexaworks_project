import { decisionLabel, reasonLabel, uiLanguage, type UiLanguage } from './presentation'

type DecisionCopy = {
  conclusion: string
  reason: string
  basis: string
  impact: string
  audit: string
  priority: string
  mandatory: string
  dependency: string
  requiredHours: string
  availableHours: string
  score: string
  veryHigh: string
  high: string
  medium: string
  low: string
  dependencyImpact: (ids: string) => string
  capacityImpact: string
  committedCustomer: (customer: string) => string
  plannedStart: string
  plannedHandover: string
  businessDeadline: string
  expectedDelay: string
  latePenalty: string
  expectedReceipt: string
  expectedAmount: string
  minimumCash: string
  safetyBuffer: string
  endingCash: string
  requiredCapacity: string
  remainingCapacity: string
  selectedOption: string
}

const copy: Record<UiLanguage, DecisionCopy> = {
  en: {
    conclusion: 'Conclusion', reason: 'Business reason', basis: 'Basis for the recommendation', impact: 'Impact', audit: 'Audit details',
    priority: 'Priority', mandatory: 'This is mandatory work', dependency: 'Depends on', requiredHours: 'Required effort', availableHours: 'Available capacity', score: 'Raw score',
    veryHigh: 'Very high', high: 'High', medium: 'Medium', low: 'Low',
    dependencyImpact: (ids) => `Complete ${ids} before this work can be scheduled.`,
    capacityImpact: 'Review available team capacity before this work can be scheduled.',
    committedCustomer: (customer) => `Delivery has already been committed to customer ${customer}.`,
    plannedStart: 'Planned start', plannedHandover: 'Expected handover', businessDeadline: 'Committed deadline', expectedDelay: 'Expected delay', latePenalty: 'Late-delivery cost', expectedReceipt: 'Expected receipt date', expectedAmount: 'Expected receipt', minimumCash: 'Lowest projected cash', safetyBuffer: 'Required safety reserve', endingCash: 'Projected ending cash', requiredCapacity: 'Effort needed', remainingCapacity: 'Team capacity remaining', selectedOption: 'Selected commercial option',
  },
  vi: {
    conclusion: 'Kết luận', reason: 'Lý do nghiệp vụ', basis: 'Cơ sở đề xuất', impact: 'Ảnh hưởng', audit: 'Chi tiết kiểm toán',
    priority: 'Mức ưu tiên', mandatory: 'Đây là công việc bắt buộc', dependency: 'Phụ thuộc vào', requiredHours: 'Khối lượng yêu cầu', availableHours: 'Năng lực khả dụng', score: 'Điểm thô',
    veryHigh: 'Rất cao', high: 'Cao', medium: 'Trung bình', low: 'Thấp',
    dependencyImpact: (ids) => `Cần hoàn thành ${ids} trước khi công việc này có thể được lên lịch.`,
    capacityImpact: 'Cần xem lại năng lực khả dụng của đội ngũ trước khi công việc này có thể được lên lịch.',
    committedCustomer: (customer) => `Đã có cam kết bàn giao cho khách hàng ${customer}.`,
    plannedStart: 'Ngày bắt đầu dự kiến', plannedHandover: 'Ngày bàn giao dự kiến', businessDeadline: 'Hạn đã cam kết', expectedDelay: 'Số ngày dự kiến chậm', latePenalty: 'Chi phí do bàn giao chậm', expectedReceipt: 'Ngày dự kiến thu tiền', expectedAmount: 'Khoản thu dự kiến', minimumCash: 'Tiền mặt thấp nhất dự kiến', safetyBuffer: 'Mức dự trữ an toàn cần giữ', endingCash: 'Tiền mặt cuối kỳ dự kiến', requiredCapacity: 'Khối lượng cần thực hiện', remainingCapacity: 'Năng lực đội ngũ còn lại', selectedOption: 'Phương án thương mại đã chọn',
  },
  ja: {
    conclusion: '結論', reason: '業務上の理由', basis: '提案の根拠', impact: '影響', audit: '監査詳細',
    priority: '優先度', mandatory: 'これは必須業務です', dependency: '前提業務', requiredHours: '必要工数', availableHours: '利用可能工数', score: '生スコア',
    veryHigh: '非常に高い', high: '高い', medium: '中', low: '低い',
    dependencyImpact: (ids) => `この業務を予定する前に ${ids} を完了する必要があります。`,
    capacityImpact: 'この業務を予定する前に、チームの利用可能工数を見直す必要があります。',
    committedCustomer: (customer) => `顧客 ${customer} への納品がすでに確約されています。`,
    plannedStart: '開始予定日', plannedHandover: '納品予定日', businessDeadline: '確約済み期限', expectedDelay: '遅延予定日数', latePenalty: '納期遅延コスト', expectedReceipt: '入金予定日', expectedAmount: '入金予定額', minimumCash: '予測最低現金', safetyBuffer: '必要安全資金', endingCash: '予測期末現金', requiredCapacity: '必要工数', remainingCapacity: '残りチーム工数', selectedOption: '選択済み商談オプション',
  },
}

const conclusions: Record<UiLanguage, Record<string, string>> = {
  en: {
    DO: 'Proceed with this work', DO_WORK_ITEM: 'Proceed with this work', SELECTED: 'Proceed with this work', SELECT_OPTION: 'Proceed with the selected option',
    DELAY: 'Delay this work', DELAYED: 'Delay this work', BLOCKED: 'Cannot proceed yet', INFEASIBLE: 'Cannot proceed under current assumptions',
    NO_BID: 'Do not pursue this opportunity', FEASIBLE: 'Can be performed', AT_RISK: 'Can proceed with risk',
  },
  vi: {
    DO: 'Thực hiện công việc này', DO_WORK_ITEM: 'Thực hiện công việc này', SELECTED: 'Thực hiện công việc này', SELECT_OPTION: 'Thực hiện phương án đã chọn',
    DELAY: 'Trì hoãn công việc này', DELAYED: 'Trì hoãn công việc này', BLOCKED: 'Chưa thể thực hiện', INFEASIBLE: 'Chưa thể thực hiện với giả định hiện tại',
    NO_BID: 'Không nên theo đuổi cơ hội này', FEASIBLE: 'Có thể thực hiện', AT_RISK: 'Có thể thực hiện nhưng có rủi ro',
  },
  ja: {
    DO: 'この業務を実行します', DO_WORK_ITEM: 'この業務を実行します', SELECTED: 'この業務を実行します', SELECT_OPTION: '選択した案を実行します',
    DELAY: 'この業務を延期します', DELAYED: 'この業務を延期します', BLOCKED: 'まだ実行できません', INFEASIBLE: '現在の前提では実行できません',
    NO_BID: 'この商談は追求しません', FEASIBLE: '実行できます', AT_RISK: 'リスクを伴いますが実行できます',
  },
}

const businessReasonCodes = new Set([
  'DEPENDENCY_NOT_SATISFIED', 'DEPENDENCY_ORDER_ENFORCED', 'PREREQUISITE_SELECTED', 'MANDATORY_ITEM_BLOCKED',
  'MANDATORY_SELECTED', 'NO_BID_CAPACITY_CONSTRAINT', 'CAPACITY_EXHAUSTED', 'DELAYED_CAPACITY_LIMIT',
  'SELECTED_BY_BUSINESS_VALUE', 'USER_DEFERRED', 'CASH_TIMING_MISMATCH', 'CASH_BUFFER_BREACH', 'BUFFER_BREACH',
  'NEGATIVE_CASH', 'NEGATIVE_CASH_EXPECTED', 'FUTURE_RECEIPT_OUTSIDE_HORIZON',
  'DEADLINE_LATE', 'SCHEDULED_AFTER_DUE_DATE', 'MANDATORY_WORK_INFEASIBLE', 'MANDATORY_WORK_OMITTED',
  'PLAN_FINANCIALLY_SAFE', 'PERSON_CAPACITY_VALID', 'COMMERCIAL_PAYMENT_OUTSIDE_HORIZON',
])

const dependencyCodes = new Set(['DEPENDENCY_NOT_SATISFIED', 'DEPENDENCY_ORDER_ENFORCED', 'PREREQUISITE_SELECTED', 'MANDATORY_ITEM_BLOCKED'])
const capacityCodes = new Set(['NO_BID_CAPACITY_CONSTRAINT', 'CAPACITY_EXHAUSTED', 'DELAYED_CAPACITY_LIMIT'])

export function decisionCopy(language?: string) {
  return copy[uiLanguage(language)]
}

export function decisionConclusion(code: string, language?: string): string {
  return conclusions[uiLanguage(language)][code] ?? decisionLabel(code, language)
}

export function businessReason(code: string | null | undefined, language?: string): string | null {
  return code && businessReasonCodes.has(code) ? reasonLabel(code, language) : null
}

export function priorityLevel(score: number | null | undefined): 'veryHigh' | 'high' | 'medium' | 'low' | null {
  if (score == null || !Number.isFinite(score)) return null
  const normalized = Math.abs(score) <= 1 ? score * 100 : score
  if (normalized >= 80) return 'veryHigh'
  if (normalized >= 60) return 'high'
  if (normalized >= 40) return 'medium'
  return 'low'
}

export function priorityLabel(score: number | null | undefined, language?: string): string | null {
  const level = priorityLevel(score)
  return level ? copy[uiLanguage(language)][level] : null
}

export function decisionImpact(code: string | null | undefined, dependencyIds: string[], language?: string): string | null {
  if (!code) return null
  const c = copy[uiLanguage(language)]
  if (dependencyCodes.has(code) && dependencyIds.length) return c.dependencyImpact(dependencyIds.join(', '))
  if (capacityCodes.has(code)) return c.capacityImpact
  return null
}

export function isTechnicalEvidenceField(key: string): boolean {
  const normalized = key.toLowerCase()
  return normalized === 'score' || normalized.endsWith('_score') || normalized === 'status' || normalized.endsWith('_status') || normalized === 'code' || normalized.endsWith('_code')
}

export type BusinessEvidence = { label: string; value: unknown; fieldKey: string }

export function businessEvidence(value: Record<string, unknown>, language?: string): BusinessEvidence[] {
  const c = copy[uiLanguage(language)]
  const fields: Record<string, string> = {
    start_date: c.plannedStart,
    completion_date: c.plannedHandover,
    delivery_reservation_completion: c.plannedHandover,
    due_date: c.businessDeadline,
    late_days: c.expectedDelay,
    late_penalty_jpy: c.latePenalty,
    receipt_date: c.expectedReceipt,
    event_date: c.expectedReceipt,
    expected_amount_jpy: c.expectedAmount,
    minimum_cash_jpy: c.minimumCash,
    minimum_buffer_jpy: c.safetyBuffer,
    ending_cash_jpy: c.endingCash,
    required_hours: c.requiredCapacity,
    available_hours: c.remainingCapacity,
    selected_option_id: c.selectedOption,
  }
  return Object.entries(fields)
    .filter(([field]) => value[field] != null)
    .map(([field, label]) => ({ label, value: value[field], fieldKey: field }))
}

export function committedCustomerFact(committed: boolean | null | undefined, customerId: string | null | undefined, language?: string): string | null {
  return committed && customerId ? copy[uiLanguage(language)].committedCustomer(customerId) : null
}
