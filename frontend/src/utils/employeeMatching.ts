import type { PlanningPerson, PlanningWorkItem } from '../workflow/types'
import { uiLanguage, type UiLanguage } from './presentation'

export type EmployeeFit = 'best' | 'partial' | 'notFit'

export interface EmployeeMatch {
  person: PlanningPerson
  fit: EmployeeFit
  availableHours: number
  requiredHours: number
  matchedSkills: string[]
  missingSkills: string[]
  matchedLanguages: string[]
  missingLanguages: string[]
  capacitySufficient: boolean
}

export function matchEmployees(
  work: PlanningWorkItem,
  people: PlanningPerson[],
  remainingHours: Map<string, number> = new Map(),
): EmployeeMatch[] {
  return people.map((person) => {
    const availableHours = remainingHours.get(person.id) ?? remainingHours.get(person.person_id ?? '') ?? person.capacity_hours
    const personSkills = person.skills ?? {}
    const personLanguages = new Set((person.languages ?? []).map((value) => value.toLowerCase()))
    const matchedSkills = work.required_skills.filter(({ skill, min_level }) => (personSkills[skill] ?? 0) >= min_level).map(({ skill }) => skill)
    const missingSkills = work.required_skills.filter(({ skill, min_level }) => (personSkills[skill] ?? 0) < min_level).map(({ skill }) => skill)
    const matchedLanguages = work.required_languages.filter((language) => personLanguages.has(language.toLowerCase()))
    const missingLanguages = work.required_languages.filter((language) => !personLanguages.has(language.toLowerCase()))
    const capacitySufficient = availableHours >= work.required_hours
    const allRequirementsMet = missingSkills.length === 0 && missingLanguages.length === 0 && capacitySufficient
    const hasRelevantMatch = matchedSkills.length > 0 || matchedLanguages.length > 0 || capacitySufficient || (work.required_skills.length === 0 && work.required_languages.length === 0 && availableHours > 0)
    const fit: EmployeeFit = allRequirementsMet ? 'best' : hasRelevantMatch ? 'partial' : 'notFit'
    return {
      person,
      fit,
      availableHours,
      requiredHours: work.required_hours,
      matchedSkills,
      missingSkills,
      matchedLanguages,
      missingLanguages,
      capacitySufficient,
    }
  }).sort((a, b) => {
    const rank: Record<EmployeeFit, number> = { best: 0, partial: 1, notFit: 2 }
    if (rank[a.fit] !== rank[b.fit]) return rank[a.fit] - rank[b.fit]
    const aMatches = a.matchedSkills.length + a.matchedLanguages.length
    const bMatches = b.matchedSkills.length + b.matchedLanguages.length
    return bMatches - aMatches || b.availableHours - a.availableHours
  })
}

const copies: Record<UiLanguage, {
  title: string; description: string; best: string; partial: string; notFit: string; noPeople: string; close: string
  skills: string; languages: string; capacity: string; matched: string; missing: string; sufficient: string; insufficient: string
}> = {
  en: {
    title: 'Suggested employees', description: 'Fit is based on the work requirements and currently available hours.', best: 'Best fit', partial: 'Partial fit', notFit: 'Not currently suitable', noPeople: 'No employees in this group.', close: 'Close suggestions',
    skills: 'Skills', languages: 'Languages', capacity: 'Available capacity', matched: 'Matched', missing: 'Missing', sufficient: 'Enough capacity', insufficient: 'Insufficient capacity',
  },
  vi: {
    title: 'Nhân sự được đề xuất', description: 'Mức độ phù hợp dựa trên yêu cầu công việc và số giờ hiện còn khả dụng.', best: 'Phù hợp nhất', partial: 'Phù hợp một phần', notFit: 'Chưa phù hợp', noPeople: 'Không có nhân sự trong nhóm này.', close: 'Đóng đề xuất',
    skills: 'Kỹ năng', languages: 'Ngôn ngữ', capacity: 'Năng lực khả dụng', matched: 'Đáp ứng', missing: 'Còn thiếu', sufficient: 'Đủ năng lực', insufficient: 'Không đủ năng lực',
  },
  ja: {
    title: '推奨担当者', description: '業務要件と現在の利用可能工数に基づく適合度です。', best: '最適', partial: '一部適合', notFit: '現時点では不適合', noPeople: 'このグループに該当者はいません。', close: '候補を閉じる',
    skills: 'スキル', languages: '言語', capacity: '利用可能工数', matched: '適合', missing: '不足', sufficient: '工数十分', insufficient: '工数不足',
  },
}

export function employeeMatchCopy(language?: string) {
  return copies[uiLanguage(language)]
}
