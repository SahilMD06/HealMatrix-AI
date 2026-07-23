import { AlertOctagon } from 'lucide-react'

import { ErrorShell } from './ErrorShell'
import { Button } from '@/components/ui/Button'

/**
 * Fallback the ErrorBoundary renders when a component throws during render.
 * `onReset` clears the boundary's error state before retrying, `detail` is
 * the caught error's message (shown so a screenshot is actually useful in
 * a bug report, never a raw stack trace).
 */
export default function ServerError({ detail, onReset }) {
  return (
    <ErrorShell
      code="500"
      icon={AlertOctagon}
      title="Something broke on our end"
      description={
        detail
          ? `The interface hit an unexpected error: "${detail}". Try reloading — if it keeps happening, note what you were doing and let the team know.`
          : 'The interface hit an unexpected error while rendering this page. Try reloading — if it keeps happening, note what you were doing and let the team know.'
      }
      primaryAction={
        <Button
          onClick={() => {
            onReset?.()
            window.location.reload()
          }}
        >
          Reload the app
        </Button>
      }
      secondaryAction={
        <Button variant="outline" onClick={() => window.location.assign('/')}>
          Go to homepage
        </Button>
      }
    />
  )
}
