import { Bot, Building2, Percent, Users } from 'lucide-react'

import { PageContainer } from '@/components/layout/PageContainer'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { StatCard } from '@/components/ui/StatCard'
import { Badge } from '@/components/ui/Badge'
import { StatusDot } from '@/components/ui/StatusDot'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/States'
import { useApi } from '@/hooks/useApi'

const ROLE_LABEL = {
  admin: 'Admin', doctor: 'Doctor', nurse: 'Nurse', pharmacist: 'Pharmacist',
  manager: 'Manager', sustainability_officer: 'Sustainability Officer',
}

/**
 * Admin dashboard: network roster, this hospital's occupancy, the agent
 * fleet's health, and the staff roster. All from existing, already-scoped
 * endpoints (/hospitals, /analytics/occupancy, /agents/status, /auth/users).
 */
export default function AdminDashboard() {
  const hospitals = useApi('/hospitals')
  const occupancy = useApi('/analytics/occupancy', { pollMs: 20000 })
  const agentStatus = useApi('/agents/status', { pollMs: 20000 })
  const roster = useApi('/auth/users')

  const o = occupancy.data
  const activeAgents = (agentStatus.data || []).filter((a) => a.implemented).length

  return (
    <PageContainer title="Admin Dashboard" subtitle="Network, capacity, agent fleet and staff roster">
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Building2}
          label="Hospitals in network"
          value={hospitals.data ? hospitals.data.length : 0}
          accent="indigo"
          delay={0}
        />
        <StatCard
          icon={Percent}
          label="This hospital's occupancy"
          value={o ? o.occupancy_rate : 0}
          unit="%"
          decimals={1}
          accent="cyan"
          delay={0.05}
        />
        <StatCard
          icon={Bot}
          label="Active agents"
          value={activeAgents}
          unit="/ 10"
          accent="emerald"
          delay={0.1}
        />
        <StatCard
          icon={Users}
          label="Staff on roster"
          value={roster.data ? roster.data.length : 0}
          accent="rose"
          delay={0.15}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Hospital network</CardTitle>
          </CardHeader>
          <CardContent>
            {hospitals.loading && !hospitals.data ? (
              <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
            ) : hospitals.error ? (
              <ErrorState error={hospitals.error} onRetry={hospitals.refetch} />
            ) : !hospitals.data?.length ? (
              <EmptyState title="No hospitals registered" />
            ) : (
              <div className="space-y-2">
                {hospitals.data.map((h) => (
                  <div key={h.id} className="flex items-center justify-between rounded-lg border border-border p-3 text-sm">
                    <div>
                      <p className="font-medium">{h.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {h.code} · {h.type} · {h.capacity?.total_beds ?? '—'} beds
                      </p>
                    </div>
                    <Badge variant={h.is_active ? 'success' : 'outline'}>
                      {h.is_active ? 'active' : 'inactive'}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Agent fleet health</CardTitle>
          </CardHeader>
          <CardContent>
            {agentStatus.loading && !agentStatus.data ? (
              <div className="space-y-2">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
            ) : agentStatus.error ? (
              <ErrorState error={agentStatus.error} onRetry={agentStatus.refetch} />
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {(agentStatus.data || []).map((agent) => (
                  <div key={agent.agent} className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs">
                    <StatusDot tone={agent.implemented ? 'online' : 'idle'} pulse={agent.implemented} />
                    <span className="truncate capitalize">{agent.agent.replace(/_/g, ' ')}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-6">
        <Card>
          <CardHeader>
            <CardTitle>Staff roster</CardTitle>
          </CardHeader>
          <CardContent>
            {roster.loading && !roster.data ? (
              <div className="space-y-2">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
            ) : roster.error ? (
              <ErrorState error={roster.error} onRetry={roster.refetch} />
            ) : !roster.data?.length ? (
              <EmptyState icon={Users} title="No staff on record yet" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="pb-2 pr-4">Name</th>
                      <th className="pb-2 pr-4">Email</th>
                      <th className="pb-2 pr-4">Role</th>
                      <th className="pb-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roster.data.map((user) => (
                      <tr key={user.id} className="border-b border-border/50 last:border-0">
                        <td className="py-2 pr-4 font-medium">{user.full_name}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{user.email}</td>
                        <td className="py-2 pr-4">
                          <Badge variant="outline">{ROLE_LABEL[user.role] || user.role}</Badge>
                        </td>
                        <td className="py-2">
                          <Badge variant={user.is_active ? 'success' : 'default'}>
                            {user.is_active ? 'active' : 'inactive'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  )
}
