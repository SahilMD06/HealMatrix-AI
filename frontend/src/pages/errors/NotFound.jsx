import { useNavigate } from 'react-router-dom'
import { Compass } from 'lucide-react'

import { ErrorShell } from './ErrorShell'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/context/AuthContext'

/** Catch-all for any unmatched route. */
export default function NotFound() {
  const navigate = useNavigate()
  const { isAuthenticated, homeRoute } = useAuth()

  return (
    <ErrorShell
      code="404"
      icon={Compass}
      title="This page doesn't exist"
      description="The link may be outdated, or the page may have moved. Check the URL, or head back to somewhere you know."
      primaryAction={
        <Button onClick={() => navigate(isAuthenticated ? homeRoute : '/')}>
          {isAuthenticated ? 'Go to my dashboard' : 'Go to homepage'}
        </Button>
      }
      secondaryAction={
        <Button variant="outline" onClick={() => navigate(-1)}>
          Go back
        </Button>
      }
    />
  )
}
