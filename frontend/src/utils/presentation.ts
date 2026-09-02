export type UiLanguage = 'en' | 'ja' | 'vi'

export function uiLanguage(language?: string): UiLanguage {
  if (language?.startsWith('ja')) return 'ja'
  if (language?.startsWith('vi')) return 'vi'
  return 'en'
}

const statusLabels: Record<UiLanguage, Record<string, string>> = {
  en: {
    PLAN_FEASIBLE: 'Plan is workable', PLAN_PARTIAL: 'Plan can only be partly delivered',
    PLAN_AT_RISK: 'Plan is at risk', PLAN_INFEASIBLE: 'Plan cannot be delivered',
    OPERATIONALLY_FEASIBLE: 'The full plan can be delivered', OPERATIONALLY_PARTIAL: 'Only part of the plan can be delivered',
    OPERATIONALLY_AT_RISK: 'Delivery is at risk', OPERATIONALLY_INFEASIBLE: 'The plan cannot be delivered',
    CASH_SAFE: 'Cash remains safe', CASH_AT_RISK: 'Cash flow is at risk',
    BUFFER_BREACH: 'Cash falls below the safety level', NEGATIVE_CASH: 'Cash will fall below zero',
    COMPLETED: 'Analysis complete', FAILED: 'Analysis failed', ACTIVE: 'Active', INACTIVE: 'Inactive',
    FEASIBLE: 'Workable', PARTIAL: 'Partly deliverable', AT_RISK: 'At risk', INFEASIBLE: 'Not deliverable',
  },
  ja: {
    PLAN_FEASIBLE: '実行可能な計画です', PLAN_PARTIAL: '計画の一部のみ実行可能です',
    PLAN_AT_RISK: '計画にリスクがあります', PLAN_INFEASIBLE: '計画を実行できません',
    OPERATIONALLY_FEASIBLE: '計画全体を実行できます', OPERATIONALLY_PARTIAL: '計画の一部のみ実行できます',
    OPERATIONALLY_AT_RISK: '実行にリスクがあります', OPERATIONALLY_INFEASIBLE: '計画を実行できません',
    CASH_SAFE: '資金は安全です', CASH_AT_RISK: '資金繰りにリスクがあります',
    BUFFER_BREACH: '現金が安全水準を下回ります', NEGATIVE_CASH: '現金残高がマイナスになります',
    COMPLETED: '分析完了', FAILED: '分析失敗', ACTIVE: '有効', INACTIVE: '無効',
    FEASIBLE: '実行可能', PARTIAL: '一部実行可能', AT_RISK: 'リスクあり', INFEASIBLE: '実行不可',
  },
  vi: {
    PLAN_FEASIBLE: 'Kế hoạch khả thi', PLAN_PARTIAL: 'Chỉ thực hiện được một phần kế hoạch',
    PLAN_AT_RISK: 'Kế hoạch có rủi ro', PLAN_INFEASIBLE: 'Không thể thực hiện kế hoạch',
    OPERATIONALLY_FEASIBLE: 'Có thể thực hiện toàn bộ kế hoạch', OPERATIONALLY_PARTIAL: 'Chỉ thực hiện được một phần kế hoạch',
    OPERATIONALLY_AT_RISK: 'Việc thực hiện có rủi ro', OPERATIONALLY_INFEASIBLE: 'Không thể thực hiện kế hoạch',
    CASH_SAFE: 'Dòng tiền an toàn', CASH_AT_RISK: 'Dòng tiền có rủi ro',
    BUFFER_BREACH: 'Tiền mặt xuống dưới mức an toàn', NEGATIVE_CASH: 'Dòng tiền sẽ xuống dưới 0',
    COMPLETED: 'Đã phân tích', FAILED: 'Phân tích thất bại', ACTIVE: 'Đang hoạt động', INACTIVE: 'Tạm dừng',
    FEASIBLE: 'Khả thi', PARTIAL: 'Chỉ thực hiện một phần', AT_RISK: 'Có rủi ro', INFEASIBLE: 'Không khả thi',
  },
}

const decisionLabels: Record<UiLanguage, Record<string, string>> = {
  en: { SELECTED: 'Do', DO: 'Do', DO_WORK_ITEM: 'Do', SELECT_OPTION: 'Choose option', DELAY: 'Delay', DELAYED: 'Delay', BLOCKED: 'Cannot proceed yet', INFEASIBLE: 'Cannot proceed', NO_BID: 'Do not pursue' },
  ja: { SELECTED: '実行', DO: '実行', DO_WORK_ITEM: '実行', SELECT_OPTION: '選択肢を選ぶ', DELAY: '延期', DELAYED: '延期', BLOCKED: 'まだ実行できません', INFEASIBLE: '実行できません', NO_BID: '参加しない' },
  vi: { SELECTED: 'Thực hiện', DO: 'Thực hiện', DO_WORK_ITEM: 'Thực hiện', SELECT_OPTION: 'Chọn phương án', DELAY: 'Trì hoãn', DELAYED: 'Trì hoãn', BLOCKED: 'Chưa thể thực hiện', INFEASIBLE: 'Không thể thực hiện', NO_BID: 'Không nên tham gia' },
}

const scenarioLabels: Record<UiLanguage, Record<string, string>> = {
  en: { EXPECTED: 'Expected', DOWNSIDE: 'Downside case', SUCCESS: 'Favourable case' },
  ja: { EXPECTED: '予測', DOWNSIDE: '悪化ケース', SUCCESS: '好調ケース' },
  vi: { EXPECTED: 'Dự kiến', DOWNSIDE: 'Tình huống xấu', SUCCESS: 'Tình huống thuận lợi' },
}

const reasonLabels: Record<UiLanguage, Record<string, string>> = {
  en: {
    CASH_TIMING_MISMATCH: 'Large receipts arrive after the planning period, so they do not solve the current cash gap.',
    CASH_BUFFER_BREACH: 'Cash falls below the minimum safety level during the plan.',
    BUFFER_BREACH: 'Cash falls below the minimum safety level during the plan.',
    NEGATIVE_CASH: 'Available cash becomes negative during the planning period.',
    NEGATIVE_CASH_EXPECTED: 'Expected cash becomes negative during the planning period.',
    FUTURE_RECEIPT_OUTSIDE_HORIZON: 'This receipt arrives after the current planning period.',
    DEPENDENCY_NOT_SATISFIED: 'This work is blocked because prerequisite work has not been completed.',
    MANDATORY_ITEM_BLOCKED: 'This mandatory work cannot proceed because a required condition is not yet satisfied.',
    CAPACITY_EXHAUSTED: 'This work cannot be scheduled because the available team capacity has been used.',
    NO_BID_CAPACITY_CONSTRAINT: 'The opportunity needs more team capacity than remains available.',
    DELAYED_CAPACITY_LIMIT: 'This work is delayed because the team does not have enough remaining capacity.',
    SELECTED_BY_BUSINESS_VALUE: 'This work was prioritised by its business value within the available capacity.',
    PREREQUISITE_SELECTED: 'This prerequisite is included because it enables other planned work.',
    MANDATORY_SELECTED: 'This work is included because it is a mandatory commitment.',
    USER_DEFERRED: 'This work is deferred in this scenario to test the management adjustment.',
    DEPENDENCY_ORDER_ENFORCED: 'Required prerequisite work is scheduled first.',
    MANDATORY_WORK_SCHEDULED: 'All mandatory commitments are included in the schedule.',
    PERSON_CAPACITY_VALID: 'No person is assigned beyond their available hours.',
    PLAN_FINANCIALLY_SAFE: 'The plan remains above the configured cash safety level.',
    DEADLINE_LATE: 'The expected handover is later than the committed deadline.',
    SCHEDULED_AFTER_DUE_DATE: 'The expected handover is later than the committed deadline.',
    MANDATORY_WORK_INFEASIBLE: 'A committed mandatory job cannot be delivered under the current conditions.',
    MANDATORY_WORK_OMITTED: 'A mandatory commitment has not yet been included in the plan.',
    COMMERCIAL_PAYMENT_OUTSIDE_HORIZON: 'Customer payment is expected after the current planning period.',
  },
  ja: {
    CASH_TIMING_MISMATCH: '大きな入金が計画期間後のため、期間内の資金不足を解消できません。',
    CASH_BUFFER_BREACH: '計画期間中に現金が最低安全水準を下回ります。', BUFFER_BREACH: '計画期間中に現金が最低安全水準を下回ります。',
    NEGATIVE_CASH: '計画期間中に現金残高がマイナスになります。', NEGATIVE_CASH_EXPECTED: '予測現金残高が計画期間中にマイナスになります。',
    FUTURE_RECEIPT_OUTSIDE_HORIZON: 'この入金は現在の計画期間後に到着します。',
    DEPENDENCY_NOT_SATISFIED: '前提業務が完了していないため、この業務は保留されています。',
    MANDATORY_ITEM_BLOCKED: '必要な条件が満たされていないため、この必須業務はまだ実行できません。',
    CAPACITY_EXHAUSTED: 'チームの利用可能工数を使い切っているため、この業務は予定できません。',
    NO_BID_CAPACITY_CONSTRAINT: 'この商談に必要な工数がチームの残り工数を超えています。',
    DELAYED_CAPACITY_LIMIT: 'チームの残り工数が不足しているため延期されました。',
    SELECTED_BY_BUSINESS_VALUE: '利用可能な工数の中で事業価値を基に優先されました。',
    PREREQUISITE_SELECTED: '他の計画作業を可能にする前提作業として選ばれました。',
    MANDATORY_SELECTED: '必須の約束であるため計画に含まれています。',
    USER_DEFERRED: '経営上の調整を検証するため、このシナリオでは延期されています。', DEPENDENCY_ORDER_ENFORCED: '必要な前提作業を先に実行します。',
    MANDATORY_WORK_SCHEDULED: 'すべての必須業務が予定されています。', PERSON_CAPACITY_VALID: '各担当者の割当は利用可能工数以内です。',
    PLAN_FINANCIALLY_SAFE: '計画期間中、現金は設定された安全水準を上回ります。',
    DEADLINE_LATE: '納品予定日が確約済みの期限を超えています。', SCHEDULED_AFTER_DUE_DATE: '納品予定日が確約済みの期限を超えています。',
    MANDATORY_WORK_INFEASIBLE: '現在の条件では、必須の確約業務を納品できません。', MANDATORY_WORK_OMITTED: '必須の確約業務がまだ計画に含まれていません。',
    COMMERCIAL_PAYMENT_OUTSIDE_HORIZON: '顧客からの入金は現在の計画期間後になる見込みです。',
  },
  vi: {
    CASH_TIMING_MISMATCH: 'Các khoản thu lớn về sau kỳ kế hoạch nên không giải quyết được thiếu hụt tiền mặt hiện tại.',
    CASH_BUFFER_BREACH: 'Tiền mặt xuống dưới mức an toàn tối thiểu trong kỳ kế hoạch.', BUFFER_BREACH: 'Tiền mặt xuống dưới mức an toàn tối thiểu trong kỳ kế hoạch.',
    NEGATIVE_CASH: 'Tiền mặt xuống dưới 0 trong kỳ kế hoạch.', NEGATIVE_CASH_EXPECTED: 'Dòng tiền dự kiến xuống dưới 0 trong kỳ kế hoạch.',
    FUTURE_RECEIPT_OUTSIDE_HORIZON: 'Khoản thu này về sau kỳ kế hoạch hiện tại.',
    DEPENDENCY_NOT_SATISFIED: 'Công việc này đang bị chặn vì công việc tiên quyết chưa hoàn thành.',
    MANDATORY_ITEM_BLOCKED: 'Công việc bắt buộc này chưa thể thực hiện vì một điều kiện cần thiết chưa được đáp ứng.',
    CAPACITY_EXHAUSTED: 'Công việc chưa thể lên lịch vì năng lực khả dụng của đội ngũ đã được sử dụng hết.',
    NO_BID_CAPACITY_CONSTRAINT: 'Cơ hội cần nhiều nguồn lực hơn phần năng lực còn lại của đội ngũ.',
    DELAYED_CAPACITY_LIMIT: 'Công việc được trì hoãn vì đội ngũ không còn đủ năng lực.',
    SELECTED_BY_BUSINESS_VALUE: 'Công việc được ưu tiên theo giá trị kinh doanh trong giới hạn nguồn lực.',
    PREREQUISITE_SELECTED: 'Công việc tiên quyết được chọn vì giúp mở đường cho công việc khác.',
    MANDATORY_SELECTED: 'Công việc được đưa vào kế hoạch vì đây là cam kết bắt buộc.',
    USER_DEFERRED: 'Công việc được trì hoãn trong kịch bản này để thử phương án điều chỉnh của quản lý.', DEPENDENCY_ORDER_ENFORCED: 'Công việc tiên quyết được bố trí hoàn thành trước.',
    MANDATORY_WORK_SCHEDULED: 'Tất cả cam kết bắt buộc đã được lên lịch.', PERSON_CAPACITY_VALID: 'Không nhân sự nào bị phân công vượt quá số giờ khả dụng.',
    PLAN_FINANCIALLY_SAFE: 'Kế hoạch duy trì tiền mặt trên mức an toàn đã đặt.',
    DEADLINE_LATE: 'Ngày bàn giao dự kiến muộn hơn thời hạn đã cam kết.', SCHEDULED_AFTER_DUE_DATE: 'Ngày bàn giao dự kiến muộn hơn thời hạn đã cam kết.',
    MANDATORY_WORK_INFEASIBLE: 'Một công việc bắt buộc đã cam kết chưa thể bàn giao trong điều kiện hiện tại.', MANDATORY_WORK_OMITTED: 'Một cam kết bắt buộc chưa được đưa vào kế hoạch.',
    COMMERCIAL_PAYMENT_OUTSIDE_HORIZON: 'Khoản thanh toán của khách hàng dự kiến về sau kỳ kế hoạch hiện tại.',
  },
}

export function statusLabel(status: string, language?: string): string {
  return statusLabels[uiLanguage(language)][status] ?? humanizeCode(status)
}

export function decisionLabel(decision: string, language?: string): string {
  return decisionLabels[uiLanguage(language)][decision] ?? humanizeCode(decision)
}

export function scenarioLabel(scenario: string, language?: string): string {
  return scenarioLabels[uiLanguage(language)][scenario] ?? humanizeCode(scenario)
}

export function reasonLabel(code: string, language?: string): string {
  return reasonLabels[uiLanguage(language)][code] ?? humanizeCode(code)
}

export function humanizeCode(code: string): string {
  return code.toLowerCase().replaceAll('_', ' ').replace(/^./, (char) => char.toUpperCase())
}

export function formatMoneyCompact(value: number | null | undefined, locale = 'en', currency = 'JPY'): string {
  if (value == null) return '—'
  const absolute = Math.abs(value)
  if (currency === 'JPY' && absolute >= 1_000_000) return `${value < 0 ? '-' : ''}¥${(absolute / 1_000_000).toLocaleString(locale, { maximumFractionDigits: 1 })}M`
  if (currency === 'JPY' && absolute >= 1_000) return `${value < 0 ? '-' : ''}¥${(absolute / 1_000).toLocaleString(locale, { maximumFractionDigits: 0 })}K`
  return new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: 0 }).format(value)
}

export function formatMoneyExact(value: number | null | undefined, locale = 'en', currency = 'JPY'): string {
  if (value == null) return '—'
  return new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: 0 }).format(value)
}

export function formatDate(value: string | null | undefined, locale = 'en'): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(`${value}T00:00:00`))
}

export function formatDateTime(value: string, locale = 'en'): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function reasonTopic(code: string, sourcePhase?: string): 'commitments' | 'capacity' | 'commercial' | 'cash' | 'dependencies' | 'risk' {
  if (code.includes('MANDATORY')) return 'commitments'
  if (code.includes('CAPACITY') || code.includes('PERSON_')) return 'capacity'
  if (code.includes('CASH') || code.includes('BUFFER') || code.includes('RECEIPT') || sourcePhase === 'CASH_FLOW') return 'cash'
  if (code.includes('DEPENDENCY') || code.includes('PREREQUISITE') || code.includes('UNLOCK')) return 'dependencies'
  if (sourcePhase === 'COMMERCIAL' || code.includes('BID') || code.includes('OPTION') || code.includes('VALUE')) return 'commercial'
  return 'risk'
}

export function statusTone(status: string): 'positive' | 'warning' | 'critical' | 'neutral' {
  if (['PLAN_FEASIBLE', 'OPERATIONALLY_FEASIBLE', 'CASH_SAFE', 'COMPLETED', 'ACTIVE'].includes(status)) return 'positive'
  if (['NEGATIVE_CASH', 'PLAN_INFEASIBLE', 'OPERATIONALLY_INFEASIBLE', 'FAILED'].includes(status)) return 'critical'
  if (status.includes('RISK') || status.includes('PARTIAL') || status === 'BUFFER_BREACH') return 'warning'
  return 'neutral'
}
