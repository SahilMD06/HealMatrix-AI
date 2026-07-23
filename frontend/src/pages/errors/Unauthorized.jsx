import { useNavigate } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'

import { ErrorShell } from './ErrorShell'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/context/AuthContext'
import { ROLE_LABELS } from '@/lib/constants'

/** Shown when a signed-in user's role does not permit the route they tried to open. */
export default function Unauthorized() {
  const navigate = useNavigate()
  const { user, homeRoute, logout } = useAuth()

  return (
    <ErrorShell
      code="403"
      icon={ShieldAlert}
      title="You don't have access to this page"
      description={
        user
          ? `Your account is signed in as ${ROLE_LABELS[user.role] || user.role}, which doesn't include this workspace. If you need access, ask a hospital administrator to update your role.`
          : "You don't have permission to view this page."
      }
      primaryAction={<Button onClick={() => navigate(homeRoute)}>Go to my dashboard</Button>}
      secondaryAction={
        <Button variant="outline" onClick={logout}>
          Sign out
        </Button>
      }
    />
  )
}
