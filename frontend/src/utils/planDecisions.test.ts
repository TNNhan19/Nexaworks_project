import { describe, expect, it } from 'vitest'
import type { PlanResult } from '../api/types'
import { workDecisionCounts, workLevelDecisions } from './planDecisions'

function planFixture(): PlanResult {
  return {
    status: 'PARTIAL',
    decisions: [
      { work_item_id: 'WORK-ARBITRARY', action_id: 'OPTION-KEEP', decision: 'SELECT_OPTION', selected_option_id: 'OPTION-KEEP', prerequisite_ids: [], unlock_trigger_ids: [], reason_codes: [] },
      { work_item_id: 'WORK-ARBITRARY', action_id: 'OPTION-SKIP', decision: 'DELAY', selected_option_id: null, prerequisite_ids: [], unlock_trigger_ids: [], reason_codes: [] },
      { work_item_id: 'WORK-LATER', action_id: 'WORK-LATER', decision: 'DELAY', selected_option_id: null, prerequisite_ids: [], unlock_trigger_ids: [], reason_codes: [] },
      { work_item_id: 'OPPORTUNITY-NOVEL', action_id: 'OPPORTUNITY-NOVEL', decision: 'NO_BID', selected_option_id: null, prerequisite_ids: [], unlock_trigger_ids: [], reason_codes: [] },
    ],
    prerequisite_closures: [], assignments: [], schedule: [],
    selected_actions: ['OPTION-KEEP'],
    delayed_actions: ['OPTION-SKIP', 'WORK-LATER'],
    no_bid_opportunities: ['OPPORTUNITY-NOVEL'],
    mandatory_infeasible: [], person_capacity: [], resource_capacity: [],
  }
}

describe('manager-facing work decision aggregation', () => {
  it('counts one work item once when it has selected and unselected options', () => {
    const plan = planFixture()
    expect(workLevelDecisions(plan)).toHaveLength(3)
    expect(workDecisionCounts(plan)).toEqual({ do: 1, delay: 1, noBid: 1 })
  })

  it('keeps arbitrary IDs and the selected option as the primary work decision', () => {
    const work = workLevelDecisions(planFixture()).find((item) => item.work_item_id === 'WORK-ARBITRARY')
    expect(work?.action_id).toBe('OPTION-KEEP')
    expect(work?.decision).toBe('SELECT_OPTION')
  })
})
