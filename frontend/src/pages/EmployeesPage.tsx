import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { workforceApi } from '../api/endpoints'
import type { Assignment, PersonCapacitySummary } from '../api/types'
import { CapacityBar } from '../components/dashboard/CapacityBar'
import { PageIntro } from '../components/business/BusinessUI'
import { interpolate, managerCopy } from '../utils/managerCopy'
import { formatDate } from '../utils/presentation'
import { useWorkflow } from '../workflow/WorkflowContext'
import { localized, workflowCopy } from '../workflow/copy'
import type { PlanningPerson } from '../workflow/types'

function skillDisplayName(skill: string): string {
  return skill
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function EmployeesPage() {
  const { i18n } = useTranslation()
  const c = managerCopy(i18n.resolvedLanguage).employees
  const wc = workflowCopy(i18n.resolvedLanguage)
  const locale = i18n.resolvedLanguage ?? 'en'
  const workflow = useWorkflow()

  const [rawPeople, setRawPeople] = useState<PlanningPerson[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedPerson, setSelectedPerson] = useState<PlanningPerson | null>(null)

  // Filter state
  const [search, setSearch] = useState('')
  const [skillFilter, setSkillFilter] = useState('all')
  const [langFilter, setLangFilter] = useState('all')
  const [availFilter, setAvailFilter] = useState('all')

  // Load people from catalog or fallback to workforce API
  useEffect(() => {
    if (workflow.catalog?.people && workflow.catalog.people.length > 0) {
      setRawPeople(workflow.catalog.people)
    } else {
      setLoading(true)
      workforceApi
        .getPeople()
        .then((data) => setRawPeople(data))
        .catch(() => setRawPeople([]))
        .finally(() => setLoading(false))
    }
  }, [workflow.catalog])

  // Merge capacity from active generation if available
  const capacityMap = useMemo(() => {
    const map = new Map<string, PersonCapacitySummary>()
    if (workflow.generation?.final_decision.capacity_summary.people) {
      for (const p of workflow.generation.final_decision.capacity_summary.people) {
        map.set(p.person_id, p)
      }
    }
    return map
  }, [workflow.generation])

  // Extract all unique skills & languages for filter dropdowns
  const allSkills = useMemo(() => {
    const set = new Set<string>()
    for (const p of rawPeople) {
      if (p.skills) {
        Object.keys(p.skills).forEach((s) => set.add(s))
      }
    }
    return Array.from(set).sort()
  }, [rawPeople])

  const allLanguages = useMemo(() => {
    const set = new Set<string>()
    for (const p of rawPeople) {
      if (p.languages) {
        p.languages.forEach((l) => set.add(l))
      }
    }
    return Array.from(set).sort()
  }, [rawPeople])

  // Filtered employees list
  const filteredPeople = useMemo(() => {
    return rawPeople.filter((person) => {
      const id = person.id || person.person_id || ''
      const name = person.name || ''
      const searchMatch =
        !search.trim() ||
        name.toLowerCase().includes(search.toLowerCase()) ||
        id.toLowerCase().includes(search.toLowerCase())

      const skillMatch =
        skillFilter === 'all' ||
        (person.skills && Object.keys(person.skills).includes(skillFilter) && (person.skills[skillFilter] || 0) > 0)

      const langMatch =
        langFilter === 'all' ||
        (person.languages && person.languages.includes(langFilter))

      const hasUnavailable = (person.unavailable_ranges && person.unavailable_ranges.length > 0)
      const capUsage = capacityMap.get(id)
      const isHighUtil = (capUsage?.utilisation_pct || 0) >= 90

      let availMatch = true
      if (availFilter === 'available') availMatch = !hasUnavailable && !isHighUtil
      else if (availFilter === 'busy') availMatch = Boolean(hasUnavailable)
      else if (availFilter === 'full') availMatch = isHighUtil

      return searchMatch && skillMatch && langMatch && availMatch
    })
  }, [rawPeople, search, skillFilter, langFilter, availFilter, capacityMap])

  // Top summary stats
  const totalEmployees = rawPeople.length
  const availableCount = rawPeople.filter(
    (p) => !p.unavailable_ranges || p.unavailable_ranges.length === 0
  ).length
  const totalCapacity = rawPeople.reduce((acc, p) => acc + (p.capacity_hours || 0), 0)
  const avgUtilization = useMemo(() => {
    if (capacityMap.size === 0 || totalCapacity === 0) return 0
    let used = 0
    capacityMap.forEach((p) => {
      used += p.used_hours
    })
    return (used / totalCapacity) * 100
  }, [capacityMap, totalCapacity])

  // Assignments for modal detail
  const personAssignments = useMemo(() => {
    if (!selectedPerson || !workflow.generation?.plan?.assignments) return []
    const personId = selectedPerson.id || selectedPerson.person_id
    return workflow.generation.plan.assignments.filter((a) => a.person_id === personId)
  }, [selectedPerson, workflow.generation])

  // Handle escape key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedPerson(null)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <div>
      <PageIntro eyebrow={c.eyebrow} title={c.title} description={c.description} />

      {/* TOP SUMMARY STATS */}
      <div className="summary-stat-grid">
        <div className="summary-stat-card">
          <div className="summary-stat-card__info">
            <span className="summary-stat-card__label">{c.totalEmployees}</span>
            <span className="summary-stat-card__value">{totalEmployees}</span>
            <span className="summary-stat-card__sub">{c.basicInfo}</span>
          </div>
          <div className="summary-stat-card__icon summary-stat-card__icon--blue">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </div>
        </div>

        <div className="summary-stat-card">
          <div className="summary-stat-card__info">
            <span className="summary-stat-card__label">{c.activeCount}</span>
            <span className="summary-stat-card__value">{availableCount}</span>
            <span className="summary-stat-card__sub">{c.available}</span>
          </div>
          <div className="summary-stat-card__icon summary-stat-card__icon--green">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
        </div>

        <div className="summary-stat-card">
          <div className="summary-stat-card__info">
            <span className="summary-stat-card__label">{c.totalCapacity}</span>
            <span className="summary-stat-card__value">{totalCapacity.toLocaleString(locale)}h</span>
            <span className="summary-stat-card__sub">{c.available}</span>
          </div>
          <div className="summary-stat-card__icon summary-stat-card__icon--purple">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </div>
        </div>

        <div className="summary-stat-card">
          <div className="summary-stat-card__info">
            <span className="summary-stat-card__label">{c.avgUtilization}</span>
            <span className="summary-stat-card__value">{avgUtilization.toFixed(1)}%</span>
            <span className="summary-stat-card__sub">{workflow.generation ? wc.progress.complete : c.unplanned}</span>
          </div>
          <div className="summary-stat-card__icon summary-stat-card__icon--orange">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="20" x2="18" y2="10" />
              <line x1="12" y1="20" x2="12" y2="4" />
              <line x1="6" y1="20" x2="6" y2="14" />
            </svg>
          </div>
        </div>
      </div>

      {/* FILTER & SEARCH TOOLBAR */}
      <div className="workforce-toolbar" role="search" aria-label={c.title}>
        <div className="workforce-search-box">
          <span className="workforce-search-icon" aria-hidden="true">🔍</span>
          <input
            type="text"
            placeholder={c.searchPlaceholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label={c.searchPlaceholder}
          />
        </div>

        <div className="workforce-filters">
          <select
            className="workforce-filter-select"
            value={skillFilter}
            onChange={(e) => setSkillFilter(e.target.value)}
            aria-label={c.filterSkill}
          >
            <option value="all">{c.allSkills}</option>
            {allSkills.map((s) => (
              <option key={s} value={s}>
                {skillDisplayName(s)}
              </option>
            ))}
          </select>

          <select
            className="workforce-filter-select"
            value={langFilter}
            onChange={(e) => setLangFilter(e.target.value)}
            aria-label={c.filterLanguage}
          >
            <option value="all">{c.allLanguages}</option>
            {allLanguages.map((l) => (
              <option key={l} value={l}>
                {l.toUpperCase()}
              </option>
            ))}
          </select>

          <select
            className="workforce-filter-select"
            value={availFilter}
            onChange={(e) => setAvailFilter(e.target.value)}
            aria-label={c.filterAvailability}
          >
            <option value="all">{c.allAvailability}</option>
            <option value="available">{c.available}</option>
            <option value="busy">{c.partiallyBusy}</option>
            <option value="full">{c.fullyUtilized}</option>
          </select>
        </div>
      </div>

      {/* EMPLOYEE CARDS GRID */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--slate-500)' }}>
          {wc.entry.description}
        </div>
      ) : filteredPeople.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 20px', background: 'white', borderRadius: '16px', border: '1px solid var(--slate-200)' }}>
          <p style={{ fontSize: '15px', color: 'var(--slate-600)', margin: 0 }}>{c.noMatching}</p>
        </div>
      ) : (
        <div className="employee-grid">
          {filteredPeople.map((person) => {
            const id = person.id || person.person_id || ''
            const capUsage = capacityMap.get(id)
            const usedHours = capUsage?.used_hours || 0
            const totalHours = person.capacity_hours || capUsage?.capacity_hours || 0
            const remainingHours = capUsage?.remaining_hours ?? totalHours
            const utilPct = capUsage?.utilisation_pct ?? (totalHours > 0 ? (usedHours / totalHours) * 100 : 0)

            const hasUnavailable = person.unavailable_ranges && person.unavailable_ranges.length > 0
            const isFull = utilPct >= 90
            const roleLabel = localized(person.role, i18n.resolvedLanguage)

            // Top skills list
            const skillsList = person.skills
              ? Object.entries(person.skills)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 3)
              : []

            const initials = person.name
              ? person.name
                  .split(' ')
                  .map((n) => n[0])
                  .join('')
                  .slice(0, 2)
                  .toUpperCase()
              : id

            return (
              <article
                key={id}
                className="employee-card"
                onClick={() => setSelectedPerson(person)}
                data-testid={`employee-card-${id}`}
                tabIndex={0}
                role="button"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setSelectedPerson(person)
                  }
                }}
              >
                <div className="employee-card__top">
                  <div className="employee-avatar">{initials}</div>
                  <div className="employee-card__meta">
                    <h3>{person.name || id}</h3>
                    <span className="employee-card__role">
                      {roleLabel || id} · <span className="secondary-id">{id}</span>
                    </span>
                  </div>
                  {hasUnavailable ? (
                    <span className="availability-tag availability-tag--busy">
                      • {c.partiallyBusy}
                    </span>
                  ) : isFull ? (
                    <span className="availability-tag availability-tag--full">
                      • {c.fullyUtilized}
                    </span>
                  ) : (
                    <span className="availability-tag availability-tag--available">
                      • {c.available}
                    </span>
                  )}
                </div>

                {/* Capacity & Usage Bar */}
                <div className="employee-card__capacity">
                  <div className="employee-card__capacity-header">
                    <strong>{interpolate(c.hoursUsed, { used: usedHours.toFixed(0), total: totalHours.toFixed(0) })}</strong>
                    <span>{utilPct.toFixed(0)}%</span>
                  </div>
                  <CapacityBar pct={utilPct} aria-label={person.name} />
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '6px', fontSize: '11px', color: 'var(--slate-500)' }}>
                    <span>{interpolate(c.hoursRemaining, { hours: remainingHours.toFixed(0) })}</span>
                  </div>
                </div>

                {/* Skills Preview */}
                {skillsList.length > 0 && (
                  <div className="employee-card__skills">
                    <span className="employee-card__section-label">{c.skillsLabel}</span>
                    <div className="skill-pills-wrap">
                      {skillsList.map(([skill, level]) => (
                        <span key={skill} className="skill-badge">
                          {skillDisplayName(skill)}
                          <span className="skill-badge__level">{level}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Languages */}
                {person.languages && person.languages.length > 0 && (
                  <div style={{ marginTop: 'auto', paddingTop: '10px' }}>
                    <div className="skill-pills-wrap">
                      {person.languages.map((lang) => (
                        <span key={lang} className="lang-badge">
                          {lang.toUpperCase()}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}

      {/* DETAIL MODAL / SLIDE-OVER PANEL */}
      {selectedPerson && (
        <div
          className="employee-modal-backdrop"
          onClick={() => setSelectedPerson(null)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-employee-name"
        >
          <div
            className="employee-modal"
            onClick={(e) => e.stopPropagation()}
            data-testid="employee-detail-modal"
          >
            <div className="employee-modal__header">
              <div className="employee-modal__profile">
                <div className="employee-modal__avatar">
                  {selectedPerson.name
                    ? selectedPerson.name
                        .split(' ')
                        .map((n) => n[0])
                        .join('')
                        .slice(0, 2)
                        .toUpperCase()
                    : selectedPerson.id}
                </div>
                <div className="employee-modal__title">
                  <h2 id="modal-employee-name">{selectedPerson.name || selectedPerson.id}</h2>
                  <p>
                    {localized(selectedPerson.role, i18n.resolvedLanguage) || selectedPerson.id} ·{' '}
                    <span className="secondary-id">{selectedPerson.id || selectedPerson.person_id}</span>
                  </p>
                </div>
              </div>
              <button
                className="modal-close-btn"
                onClick={() => setSelectedPerson(null)}
                aria-label={c.close}
              >
                ✕
              </button>
            </div>

            <div className="employee-modal__body">
              {/* Capacity Section */}
              <div className="modal-section">
                <h3>{c.totalCapacity} & {c.avgUtilization}</h3>
                {(() => {
                  const id = selectedPerson.id || selectedPerson.person_id || ''
                  const capUsage = capacityMap.get(id)
                  const used = capUsage?.used_hours || 0
                  const total = selectedPerson.capacity_hours || capUsage?.capacity_hours || 0
                  const remaining = capUsage?.remaining_hours ?? total
                  const pct = capUsage?.utilisation_pct ?? (total > 0 ? (used / total) * 100 : 0)

                  return (
                    <div>
                      <dl className="capacity-metrics-strip" style={{ margin: '0 0 14px' }}>
                        <div className="capacity-metric-item">
                          <dt>{c.totalCapacity}</dt>
                          <dd>{total}h</dd>
                        </div>
                        <div className="capacity-metric-item">
                          <dt>{managerCopy(i18n.resolvedLanguage).dashboard.usedHours}</dt>
                          <dd>{used.toFixed(1)}h</dd>
                        </div>
                        <div className="capacity-metric-item">
                          <dt>{managerCopy(i18n.resolvedLanguage).dashboard.remainingHours}</dt>
                          <dd>{remaining.toFixed(1)}h</dd>
                        </div>
                      </dl>
                      <CapacityBar pct={pct} aria-label={selectedPerson.name} />
                      <div style={{ textAlign: 'right', marginTop: '6px', fontSize: '12px', color: 'var(--slate-600)' }}>
                        <strong>{pct.toFixed(1)}% {c.avgUtilization}</strong>
                      </div>
                    </div>
                  )
                })()}
              </div>

              {/* Hourly Cost if present */}
              {selectedPerson.hourly_cost_jpy != null && (
                <div className="modal-section">
                  <h3>{c.hourlyCost}</h3>
                  <p style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--navy-900)' }}>
                    ¥{selectedPerson.hourly_cost_jpy.toLocaleString(locale)} / h
                  </p>
                </div>
              )}

              {/* Unavailable Date Ranges */}
              <div className="modal-section">
                <h3>{c.unavailableRanges}</h3>
                {selectedPerson.unavailable_ranges && selectedPerson.unavailable_ranges.length > 0 ? (
                  <div className="modal-unavailable-list">
                    {selectedPerson.unavailable_ranges.map((range, idx) => (
                      <div key={idx} className="modal-unavailable-item">
                        📅 {formatDate(range.start, locale)} – {formatDate(range.end, locale)}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ margin: 0, color: 'var(--slate-500)', fontSize: '13px' }}>{c.noUnavailable}</p>
                )}
              </div>

              {/* Skills & Levels */}
              <div className="modal-section">
                <h3>{c.allSkillsHeading}</h3>
                {selectedPerson.skills && Object.keys(selectedPerson.skills).length > 0 ? (
                  <div className="modal-skills-grid">
                    {Object.entries(selectedPerson.skills).map(([skill, level]) => (
                      <div key={skill} className="modal-skill-item">
                        <span>{skillDisplayName(skill)}</span>
                        <div className="modal-skill-stars" title={`Level ${level} / 5`}>
                          {[1, 2, 3, 4, 5].map((star) => (
                            <div
                              key={star}
                              className={`modal-skill-star ${star <= level ? 'modal-skill-star--active' : ''}`}
                            />
                          ))}
                          <span style={{ marginLeft: '6px', fontSize: '11px', fontWeight: 700, color: 'var(--slate-600)' }}>
                            {level}/5
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ margin: 0, color: 'var(--slate-500)', fontSize: '13px' }}>—</p>
                )}
              </div>

              {/* Languages */}
              <div className="modal-section">
                <h3>{c.languagesLabel}</h3>
                <div className="skill-pills-wrap">
                  {selectedPerson.languages && selectedPerson.languages.length > 0 ? (
                    selectedPerson.languages.map((l) => (
                      <span key={l} className="lang-badge" style={{ padding: '6px 12px', fontSize: '12px' }}>
                        🌐 {l.toUpperCase()}
                      </span>
                    ))
                  ) : (
                    <span style={{ color: 'var(--slate-500)', fontSize: '13px' }}>—</span>
                  )}
                </div>
              </div>

              {/* Assigned Work Items in Plan */}
              <div className="modal-section">
                <h3>{c.assignmentsHeading}</h3>
                {!workflow.generation ? (
                  <div style={{ padding: '14px', background: '#f8fafc', borderRadius: '10px', color: 'var(--slate-500)', fontSize: '13px' }}>
                    {c.unplanned}
                  </div>
                ) : personAssignments.length === 0 ? (
                  <div style={{ padding: '14px', background: '#f8fafc', borderRadius: '10px', color: 'var(--slate-500)', fontSize: '13px' }}>
                    {c.noAssignments}
                  </div>
                ) : (
                  <div className="modal-assignments-list">
                    {personAssignments.map((assignment: Assignment, idx: number) => {
                      const workItem = workflow.catalog?.work_items.find(
                        (w) => w.id === assignment.action_id || assignment.action_id.startsWith(w.id)
                      )
                      const title = localized(workItem?.title, i18n.resolvedLanguage) || assignment.action_id
                      const roleName =
                        assignment.assignment_role === 'OWNER' ? c.ownerRole : c.contributorRole

                      return (
                        <div key={idx} className="modal-assignment-card">
                          <div>
                            <h4>{title}</h4>
                            <span>
                              {assignment.action_id} · <strong>{roleName}</strong>
                            </span>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <strong style={{ fontSize: '15px', color: 'var(--navy-950)' }}>
                              {assignment.assigned_hours}h
                            </strong>
                            <div style={{ fontSize: '11px', color: 'var(--slate-500)' }}>
                              {assignment.skills_covered.map(skillDisplayName).join(', ')}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
