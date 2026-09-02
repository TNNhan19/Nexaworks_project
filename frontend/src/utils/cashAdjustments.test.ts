import { describe, expect, it } from 'vitest'
import type { CashFlowResult, PlanResult } from '../api/types'
import type { PlanningCatalog } from '../workflow/types'
import { buildCashAdjustmentAdvice } from './cashAdjustments'

const event = (sourceId: string, amount: number) => ({
  event_id: `E-${sourceId}`, date: '2035-01-02', source_type: 'WORK_ITEM', source_id: sourceId,
  event_type: 'WORK_DIRECT_COST', scenario: 'EXPECTED', amount_jpy: amount,
  direction: 'OUTFLOW' as const, deterministic: true, probability: null,
  timing_basis: 'test', outside_horizon: false, evidence: {},
})

const cash = {
  overall_status: 'NEGATIVE_CASH', operational_plan_status: 'PARTIAL', starting_cash_jpy: 1_000, minimum_buffer_jpy: 500,
  scenarios: { EXPECTED: {
    scenario: 'EXPECTED', status: 'NEGATIVE_CASH',
    timeline: [
      { date: '2035-01-01', opening_cash_jpy: 1_000, cash_in_jpy: 0, cash_out_jpy: 100, net_change_jpy: -100, closing_cash_jpy: 400, minimum_buffer_jpy: 500, buffer_headroom_jpy: -100, buffer_breach: true, negative_cash: false, events: [event('LOW', 100)] },
      { date: '2035-01-02', opening_cash_jpy: 400, cash_in_jpy: 0, cash_out_jpy: 600, net_change_jpy: -600, closing_cash_jpy: -100, minimum_buffer_jpy: 500, buffer_headroom_jpy: -600, buffer_breach: true, negative_cash: true, events: [event('HIGHER', 600)] },
    ],
    in_horizon_events: [event('LOW', 100), event('HIGHER', 600)], future_events: [], total_cash_in_jpy: 0, total_cash_out_jpy: 700, event_totals_jpy: {}, minimum_cash_jpy: -100, minimum_cash_date: '2035-01-02', ending_cash_jpy: -100, first_buffer_breach_date: '2035-01-01', days_below_buffer: 2, buffer_breach_dates: ['2035-01-01', '2035-01-02'], negative_cash_dates: ['2035-01-02'],
  } },
  future_events: [{ ...event('FUTURE', 2_000), event_id: 'FUTURE', date: '2035-02-01', event_type: 'WORK_CASH_RECEIPT', amount_jpy: 2_000, direction: 'INFLOW', outside_horizon: true }],
  reasons: [], warnings: [], assumptions_used: {},
} as unknown as CashFlowResult

const plan = {
  status: 'PARTIAL', decisions: [
    { work_item_id: 'LOW', action_id: 'LOW', decision: 'DO', selected_option_id: null, prerequisite_ids: [], unlock_trigger_ids: [], reason_codes: [], business_value_score: 1 },
    { work_item_id: 'HIGHER', action_id: 'HIGHER', decision: 'DO', selected_option_id: null, prerequisite_ids: [], unlock_trigger_ids: [], reason_codes: [], business_value_score: 2 },
  ], prerequisite_closures: [], assignments: [], schedule: [], selected_actions: ['LOW', 'HIGHER'], delayed_actions: [], no_bid_opportunities: [], mandatory_infeasible: [], person_capacity: [], resource_capacity: [],
} as PlanResult

const catalog = {
  summary: {} as any, company: { name: 'T', starting_cash_jpy: 1_000, minimum_cash_buffer_jpy: 500 },
  work_items: [
    { id: 'LOW', title: 'Low-value work', type: 'internal', mandatory: false, dependencies: [] },
    { id: 'HIGHER', title: 'Higher-value work', type: 'internal', mandatory: false, dependencies: [] },
  ], people: [], customers: [], shared_resources: [], commercial_options: [], portfolio_effects: [],
} as unknown as PlanningCatalog

describe('cash adjustment advisor', () => {
  it('separates the zero-cash gap from the preferred safety-buffer gap', () => {
    const advice = buildCashAdjustmentAdvice(cash, plan, catalog)!
    expect(advice.band).toBe('NEGATIVE')
    expect(advice.gapToAvoidNegativeJpy).toBe(100)
    expect(advice.gapToSafetyBufferJpy).toBe(600)
    expect(advice.requiredStartingCashJpy).toBe(1_600)
  })

  it('ranks optional work by business score and quantifies cumulative relief', () => {
    const advice = buildCashAdjustmentAdvice(cash, plan, catalog)!
    expect(advice.deferrals.map((item) => item.workItemId)).toEqual(['LOW', 'HIGHER'])
    expect(advice.deferrals[0].projectedEndingCashJpy).toBe(0)
    expect(advice.deferralBundle?.liquidityReliefJpy).toBe(700)
    expect(advice.deferralBundle?.reachesSafetyBuffer).toBe(true)
    expect(advice.receiptCandidates[0].workItemId).toBe('FUTURE')
  })
})
