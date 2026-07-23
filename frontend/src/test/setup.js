import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

// RTL's auto-cleanup only registers itself when `afterEach` is a global; this
// project's vitest config keeps globals off (matching its explicit-import
// style elsewhere), so cleanup is wired here instead — without it, DOM from
// one test would leak into the next within the same file.
afterEach(() => {
  cleanup()
})

// jsdom does not implement matchMedia. ThemeContext (system-theme detection)
// and useAnimatedCounter (prefers-reduced-motion) both call it unconditionally,
// so every test needs a stub rather than each test file reinventing one.
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })
}

// jsdom's requestAnimationFrame support is inconsistent across versions;
// useAnimatedCounter drives its easing loop with it, so a minimal polyfill
// keeps that hook from throwing in components that render a StatCard.
if (!window.requestAnimationFrame) {
  window.requestAnimationFrame = (cb) => setTimeout(() => cb(performance.now()), 16)
  window.cancelAnimationFrame = (id) => clearTimeout(id)
}
