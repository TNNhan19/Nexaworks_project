export const navigationItems = [
  { key: 'overview', path: '/dashboard', icon: 'grid' },
  { key: 'planning', path: '/planning', icon: 'layers' },
  { key: 'workItems', path: '/work-items', icon: 'insight' },
  { key: 'employees', path: '/employees', icon: 'users' },
  { key: 'executionPlan', path: '/plan', icon: 'calendar' },
  { key: 'cashFlow', path: '/cash-flow', icon: 'cash' },
  { key: 'scenarios', path: '/scenarios', icon: 'layers' },
  { key: 'comparison', path: '/comparison', icon: 'compare' },
  { key: 'explanations', path: '/explanations', icon: 'insight' },
] as const

export type NavigationKey = typeof navigationItems[number]['key']
