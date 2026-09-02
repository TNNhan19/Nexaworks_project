import type { CashFlowResult, CashScenarioResult, PlanDecision, PlanResult } from '../api/types'
import type { PlanningCatalog, PlanningWorkItem } from '../workflow/types'

export type LiquidityBand = 'SAFE' | 'AT_RISK' | 'NEGATIVE'

export interface DeferralAdvice {
  workItemId: string
  actionId: string
  title: PlanningWorkItem['title']
  businessValueScore: number | null
  liquidityReliefJpy: number
  projectedMinimumCashJpy: number
  projectedEndingCashJpy: number
  avoidsNegativeCash: boolean
  reachesSafetyBuffer: boolean
}

export interface ReceiptAdvice {
  workItemId: string
  amountJpy: number
  currentReceiptDate: string
}

export interface CashAdjustmentAdvice {
  band: LiquidityBand
  gapToAvoidNegativeJpy: number
  gapToSafetyBufferJpy: number
  expectedMinimumCashJpy: number
  expectedEndingCashJpy: number
  firstUnsafeDate: string | null
  deferrals: DeferralAdvice[]
  deferralBundle: DeferralAdvice | null
  receiptCandidates: ReceiptAdvice[]
  requiredStartingCashJpy: number
  residualFundingAfterDeferralsJpy: number
}

const isOutflow = (direction: string) => direction === 'OUTFLOW' || direction === 'OUT'
const isInflow = (direction: string) => direction === 'INFLOW' || direction === 'IN'

function selectedDecision(decision: PlanDecision) {
  return ['DO', 'SELECT_OPTION', 'ENABLING_PREREQUISITE', 'SELECTED'].includes(decision.decision)
}

function projectWithoutSources(expected: CashScenarioResult, sourceIds: Set<string>) {
  let cumulative = 0
  let minimum = Number.POSITIVE_INFINITY
  let ending = expected.ending_cash_jpy
  for (const day of expected.timeline) {
    for (const event of day.events) {
      if (!sourceIds.has(event.source_id)) continue
      if (isOutflow(event.direction)) cumulative += event.amount_jpy
      if (isInflow(event.direction)) cumulative -= event.amount_jpy
    }
    const projected = day.closing_cash_jpy + cumulative
    minimum = Math.min(minimum, projected)
    ending = projected
  }
  return {
    minimum: Number.isFinite(minimum) ? minimum : expected.minimum_cash_jpy,
    ending,
    relief: ending - expected.ending_cash_jpy,
  }
}

function adviceForDecision(
  decision: PlanDecision,
  work: PlanningWorkItem,
  expected: CashScenarioResult,
  buffer: number,
): DeferralAdvice | null {
  const projected = projectWithoutSources(expected, new Set([decision.work_item_id, decision.action_id]))
  if (projected.relief <= 0) return null
  return {
    workItemId: decision.work_item_id,
    actionId: decision.action_id,
    title: work.title,
    businessValueScore: decision.business_value_score ?? null,
    liquidityReliefJpy: projected.relief,
    projectedMinimumCashJpy: projected.minimum,
    projectedEndingCashJpy: projected.ending,
    avoidsNegativeCash: projected.minimum >= 0,
    reachesSafetyBuffer: projected.minimum >= buffer,
  }
}

export function buildCashAdjustmentAdvice(
  cash: CashFlowResult,
  plan: PlanResult,
  catalog: PlanningCatalog,
): CashAdjustmentAdvice | null {
  const expected = cash.scenarios.EXPECTED
  if (!expected) return null
  const buffer = cash.minimum_buffer_jpy
  const minimum = expected.minimum_cash_jpy
  const band: LiquidityBand = minimum >= buffer ? 'SAFE' : minimum >= 0 ? 'AT_RISK' : 'NEGATIVE'
  const gapToAvoidNegativeJpy = Math.max(0, -minimum)
  const gapToSafetyBufferJpy = Math.max(0, buffer - minimum)
  const protectedPrerequisites = new Set(
    plan.decisions.filter(selectedDecision).flatMap((decision) => decision.prerequisite_ids),
  )
  const workMap = new Map(catalog.work_items.map((work) => [work.id, work]))
  const deferrals = plan.decisions
    .filter((decision) => decision.decision === 'DO' || decision.decision === 'SELECT_OPTION')
    .flatMap((decision) => {
      const work = workMap.get(decision.work_item_id)
      if (!work || work.mandatory || protectedPrerequisites.has(work.id)) return []
      if (work.type === 'cash_collection' || work.type === 'sales_opportunity') return []
      const advice = adviceForDecision(decision, work, expected, buffer)
      return advice ? [advice] : []
    })
    .sort((a, b) => {
      const scoreA = a.businessValueScore ?? Number.POSITIVE_INFINITY
      const scoreB = b.businessValueScore ?? Number.POSITIVE_INFINITY
      return scoreA - scoreB || b.liquidityReliefJpy - a.liquidityReliefJpy || a.workItemId.localeCompare(b.workItemId)
    })

  const bundleSources = new Set<string>()
  for (const item of deferrals) {
    bundleSources.add(item.workItemId)
    bundleSources.add(item.actionId)
  }
  const bundleProjection = bundleSources.size ? projectWithoutSources(expected, bundleSources) : null
  const deferralBundle = bundleProjection ? {
    workItemId: deferrals.map((item) => item.workItemId).join(','),
    actionId: deferrals.map((item) => item.actionId).join(','),
    title: '',
    businessValueScore: null,
    liquidityReliefJpy: bundleProjection.relief,
    projectedMinimumCashJpy: bundleProjection.minimum,
    projectedEndingCashJpy: bundleProjection.ending,
    avoidsNegativeCash: bundleProjection.minimum >= 0,
    reachesSafetyBuffer: bundleProjection.minimum >= buffer,
  } satisfies DeferralAdvice : null

  const receiptCandidates = cash.future_events
    .filter((event) => event.scenario === 'EXPECTED' && event.event_type === 'WORK_CASH_RECEIPT' && event.amount_jpy > 0)
    .map((event) => ({ workItemId: event.source_id, amountJpy: event.amount_jpy, currentReceiptDate: event.date }))
    .filter((item, index, items) => items.findIndex((candidate) => candidate.workItemId === item.workItemId) === index)
    .sort((a, b) => b.amountJpy - a.amountJpy || a.workItemId.localeCompare(b.workItemId))

  const residualFundingAfterDeferralsJpy = Math.max(
    0,
    buffer - (bundleProjection?.minimum ?? minimum),
  )
  return {
    band,
    gapToAvoidNegativeJpy,
    gapToSafetyBufferJpy,
    expectedMinimumCashJpy: minimum,
    expectedEndingCashJpy: expected.ending_cash_jpy,
    firstUnsafeDate: expected.first_buffer_breach_date,
    deferrals,
    deferralBundle,
    receiptCandidates,
    requiredStartingCashJpy: cash.starting_cash_jpy + gapToSafetyBufferJpy,
    residualFundingAfterDeferralsJpy,
  }
}
