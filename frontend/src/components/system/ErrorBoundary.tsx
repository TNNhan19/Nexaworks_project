import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { failed: boolean }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }
  static getDerivedStateFromError(): State { return { failed: true } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('Application render failed', error, info) }
  render() {
    if (this.state.failed) {
      return <main className="fatal-error"><h1>Something went wrong</h1><p>Reload the application to try again.</p></main>
    }
    return this.props.children
  }
}
