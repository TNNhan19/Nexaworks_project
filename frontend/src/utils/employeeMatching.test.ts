import { describe, expect, it } from 'vitest'
import { matchEmployees } from './employeeMatching'

const work = {
  id: 'W-1', required_hours: 40, required_skills: [{ skill: 'react', min_level: 3 }, { skill: 'sql', min_level: 2 }], required_languages: ['ja'],
} as any

describe('employee matching', () => {
  it('groups employees using only requirements and available capacity', () => {
    const people = [
      { id: 'BEST', name: 'Best', capacity_hours: 80, skills: { react: 4, sql: 3 }, languages: ['ja'] },
      { id: 'PARTIAL', name: 'Partial', capacity_hours: 80, skills: { react: 4 }, languages: ['en'] },
      { id: 'NO', name: 'No', capacity_hours: 10, skills: {}, languages: ['en'] },
    ] as any
    const result = matchEmployees(work, people)
    expect(result.map((entry) => [entry.person.id, entry.fit])).toEqual([['BEST', 'best'], ['PARTIAL', 'partial'], ['NO', 'notFit']])
    expect(result[1].missingSkills).toEqual(['sql'])
    expect(result[1].missingLanguages).toEqual(['ja'])
  })

  it('uses remaining plan capacity when it is available', () => {
    const people = [{ id: 'P-1', name: 'Person', capacity_hours: 80, skills: { react: 4, sql: 3 }, languages: ['ja'] }] as any
    expect(matchEmployees(work, people, new Map([['P-1', 12]]))[0]).toMatchObject({ fit: 'partial', availableHours: 12, capacitySufficient: false })
  })
})
