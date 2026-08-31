import { useTranslation } from 'react-i18next'
import type { FinancialStatus, OperationalStatus, OverallStatus } from '../../api/types'

type AnyStatus = OverallStatus | OperationalStatus | FinancialStatus | string

function badgeClass(status: AnyStatus): string {
  switch (status) {
    case 'PLAN_FEASIBLE':
    case 'OPERATIONALLY_FEASIBLE':
    case 'CASH_SAFE':
      return 'status-badge status-badge--feasible'
    case 'PLAN_PARTIAL':
    case 'OPERATIONALLY_PARTIAL':
      return 'status-badge status-badge--partial'
    case 'PLAN_AT_RISK':
    case 'OPERATIONALLY_AT_RISK':
    case 'CASH_AT_RISK':
      return 'status-badge status-badge--at-risk'
    case 'BUFFER_BREACH':
      return 'status-badge status-badge--breach'
    case 'NEGATIVE_CASH':
      return 'status-badge status-badge--negative'
    case 'PLAN_INFEASIBLE':
    case 'OPERATIONALLY_INFEASIBLE':
      return 'status-badge status-badge--infeasible'
    default:
      return 'status-badge status-badge--infeasible'
  }
}

interface StatusBadgeProps {
  status: AnyStatus
  /** Optional data-testid; defaults to status value */
  testId?: string
}

export function StatusBadge({ status, testId }: StatusBadgeProps) {
  const { t } = useTranslation()
  const label = t(`status.${status}`, { defaultValue: status })
  return (
    <span className={badgeClass(status)} data-testid={testId ?? `badge-${status}`}>
      {label}
    </span>
  )
}
