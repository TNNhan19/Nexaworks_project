import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { ErrorBoundary } from './components/system/ErrorBoundary'
import { DashboardPage } from './pages/DashboardPage'
import { PlanPage } from './pages/PlanPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { ScenariosPage } from './pages/ScenariosPage'

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="scenarios" element={<ScenariosPage />} />
          <Route path="plan" element={<PlanPage />} />
          <Route path="cash-flow" element={<PlaceholderPage page="cashFlow" />} />
          <Route path="comparison" element={<PlaceholderPage page="comparison" />} />
          <Route path="explanations" element={<PlaceholderPage page="explanations" />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  )
}
