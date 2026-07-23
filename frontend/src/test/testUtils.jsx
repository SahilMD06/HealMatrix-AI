import { render } from '@testing-library/react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'

import { ThemeProvider } from '@/context/ThemeContext'

/** Stands in for DashboardLayout: pages built on PageContainer call
 * useOutletContext() for openMenu/openSearch, which only resolves inside an
 * <Outlet> a parent route rendered — this recreates that one contract without
 * pulling in the whole app shell (sidebar, command palette, auth guard). */
function OutletHost() {
  return <Outlet context={{ openMenu: () => {}, openSearch: () => {} }} />
}

/**
 * Renders a dashboard page the way the real router does: inside a
 * MemoryRouter, under the same Outlet-context contract DashboardLayout
 * provides, and inside ThemeProvider (the Header reads theme state). Any page
 * that calls useApi/useApiHealth still needs `@/services/api` mocked by the
 * calling test — this helper only supplies routing/theme context.
 */
export function renderPage(ui, { route = '/' } = {}) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route element={<OutletHost />}>
            <Route path="/" element={ui} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  )
}
