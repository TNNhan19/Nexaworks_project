import type { PlanDecision, PlanResult } from '../api/types'

export type DecisionGroup = 'do' | 'delay' | 'noBid'

const selectedDecisions = new Set(['SELECTED', 'DO', 'DO_WORK_ITEM', 'SELECT_OPTION', 'ENABLING_PREREQUISITE'])

export function decisionGroup(item: PlanDecision, plan: PlanResult): DecisionGroup {
  if (item.decision === 'NO_BID' || plan.no_bid_opportunities.includes(item.work_item_id)) return 'noBid'
  if (plan.selected_actions.includes(item.action_id) || selectedDecisions.has(item.decision)) return 'do'
  return 'delay'
}

function placeholder(workItemId: string, actionId: string, decision: string): PlanDecision {
  return {
    work_item_id: workItemId,
    action_id: actionId,
    decision,
    selected_option_id: null,
    prerequisite_ids: [],
    unlock_trigger_ids: [],
    reason_codes: [],
  }
}

/**
 * Convert action-level planner output into one manager-facing decision per work
 * item. Commercial alternatives remain available as evidence on the work card,
 * but are never counted as additional work.
 */
export function workLevelDecisions(plan: PlanResult): PlanDecision[] {
  const decisions = [...plan.decisions]
  for (const actionId of plan.selected_actions) {
    if (!decisions.some((item) => item.action_id === actionId)) {
      decisions.push(placeholder(actionId, actionId, 'SELECTED'))
    }
  }
  for (const actionId of plan.delayed_actions) {
    if (!decisions.some((item) => item.action_id === actionId)) {
      decisions.push(placeholder(actionId, actionId, 'DELAYED'))
    }
  }
  for (const workItemId of plan.no_bid_opportunities) {
    if (!decisions.some((item) => item.work_item_id === workItemId)) {
      decisions.push(placeholder(workItemId, workItemId, 'NO_BID'))
    }
  }

  const rank: Record<DecisionGroup, number> = { do: 3, noBid: 2, delay: 1 }
  const byWork = new Map<string, PlanDecision>()
  for (const decision of decisions) {
    const current = byWork.get(decision.work_item_id)
    if (!current || rank[decisionGroup(decision, plan)] > rank[decisionGroup(current, plan)]) {
      byWork.set(decision.work_item_id, decision)
    }
  }
  return [...byWork.values()]
}

export function workDecisionCounts(plan: PlanResult) {
  const counts: Record<DecisionGroup, number> = { do: 0, delay: 0, noBid: 0 }
  for (const decision of workLevelDecisions(plan)) counts[decisionGroup(decision, plan)] += 1
  return counts
}
