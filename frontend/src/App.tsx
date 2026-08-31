import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { ErrorBoundary } from './components/system/ErrorBoundary'
import { DashboardPage } from './pages/DashboardPage'
import { PlaceholderPage } from './pages/PlaceholderPage'

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="scenarios" element={<PlaceholderPage page="scenarios" />} />
          <Route path="plan" element={<PlaceholderPage page="plan" />} />
          <Route path="cash-flow" element={<PlaceholderPage page="cashFlow" />} />
          <Route path="comparison" element={<PlaceholderPage page="comparison" />} />
          <Route path="explanations" element={<PlaceholderPage page="explanations" />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  )
}
