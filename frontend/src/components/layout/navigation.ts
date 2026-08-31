export const navigationItems = [
  { key: 'dashboard', path: '/dashboard', icon: 'grid' },
  { key: 'scenarios', path: '/scenarios', icon: 'layers' },
  { key: 'plan', path: '/plan', icon: 'calendar' },
  { key: 'cashFlow', path: '/cash-flow', icon: 'cash' },
  { key: 'comparison', path: '/comparison', icon: 'compare' },
  { key: 'explanations', path: '/explanations', icon: 'insight' },
] as const

export type NavigationKey = typeof navigationItems[number]['key']
