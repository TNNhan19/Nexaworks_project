import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { ErrorBoundary } from './components/system/ErrorBoundary'
import { DashboardPage } from './pages/DashboardPage'
import { PlanPage } from './pages/PlanPage'
import { ScenariosPage } from './pages/ScenariosPage'
import { CashFlowPage } from './pages/CashFlowPage'
import { ComparisonPage } from './pages/ComparisonPage'
import { ExplanationsPage } from './pages/ExplanationsPage'
import { PlanningPage } from './pages/PlanningPage'
import { WorkItemsPage } from './pages/WorkItemsPage'
import { EmployeesPage } from './pages/EmployeesPage'
import { WorkflowProvider } from './workflow/WorkflowContext'

export default function App() {
  return (
    <ErrorBoundary>
      <WorkflowProvider>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="planning" element={<PlanningPage />} />
          <Route path="work-items" element={<WorkItemsPage />} />
          <Route path="employees" element={<EmployeesPage />} />
          <Route path="scenarios" element={<ScenariosPage />} />
          <Route path="plan" element={<PlanPage />} />
          <Route path="cash-flow" element={<CashFlowPage />} />
          <Route path="comparison" element={<ComparisonPage />} />
          <Route path="explanations" element={<ExplanationsPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
      </WorkflowProvider>
    </ErrorBoundary>
  )
}
