import { lazy, Suspense } from "react"
import { Navigate, Route, Routes } from "react-router-dom"

const LandingPage = lazy(() =>
  import("@/features/landing/landing-page").then((module) => ({
    default: module.LandingPage,
  }))
)
const ScanPage = lazy(() =>
  import("@/features/scan/scan-page").then((module) => ({
    default: module.ScanPage,
  }))
)
const SummaryPage = lazy(() =>
  import("@/features/summary/summary-page").then((module) => ({
    default: module.SummaryPage,
  }))
)
const WorkspacePage = lazy(() =>
  import("@/features/workspace/workspace-page").then((module) => ({
    default: module.WorkspacePage,
  }))
)

function RouteFallback() {
  return (
    <main className="route-fallback" aria-live="polite" aria-busy="true">
      <span />
      <strong>Loading verified workspace</strong>
      <small>Preparing the local evidence projection…</small>
    </main>
  )
}

export function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/scan/:jobId" element={<ScanPage />} />
        <Route path="/workspace/:kind/:id" element={<WorkspacePage />} />
        <Route path="/summary/:kind/:id" element={<SummaryPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

export default App
