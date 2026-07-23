import { useState } from 'react'
import { Activity, AlertTriangle, Clock, Users } from 'lucide-react'

import { PageContainer } from '@/components/layout/PageContainer'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { StatCard } from '@/components/ui/StatCard'
import { Button } from '@/components/ui/Button'
import { TriageQueue } from '@/components/clinical/TriageQueue'
import { ArrivalForm } from '@/components/clinical/ArrivalForm'
import { AgentRationale } from '@/components/agents/AgentRationale'
import { TriageBadge } from '@/components/ui/TriageBadge'
import { useApi } from '@/hooks/useApi'

/**
 * Doctor dashboard: the live triage queue, a new-arrival intake that runs the
 * triage agent, and the agent's rationale for the most recent decision.
 */
export default function DoctorDashboard() {
  const overview = useApi('/analytics/overview', { pollMs: 20000 })
  const queue = useApi('/admissions/queue', { pollMs: 15000 })
  const [lastResult, setLastResult] = useState(null)

  const kpi = overview.data || {}

  function handleArrival(result) {
    setLastResult(result)
    queue.refetch()
    overview.refetch()
  }

  return (
    <PageContainer
      title="Doctor Dashboard"
      subtitle="Live triage queue and AI-assisted intake"
      actions={<Button size="sm" variant="outline" onClick={queue.refetch}>Refresh queue</Button>}
    >
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Users} label="Active census" value={kpi.census ?? 0} accent="indigo" delay={0} />
        <StatCard icon={AlertTriangle} label="Critical (ESI ≤ 2)" value={kpi.critical_active ?? 0} accent="rose" delay={0.05} />
        <StatCard icon={Clock} label="Admissions 24h" value={kpi.admissions_24h ?? 0} accent="cyan" delay={0.1} />
        <StatCard icon={Activity} label="Agent decisions 24h" value={kpi.agent_decisions_24h ?? 0} accent="emerald" delay={0.15} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Triage Queue</CardTitle>
            </CardHeader>
            <CardContent>
              <TriageQueue
                data={queue.data}
                loading={queue.loading}
                error={queue.error}
                onRetry={queue.refetch}
              />
            </CardContent>
          </Card>

          {lastResult && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <TriageBadge level={lastResult.triage.esi_level} />
                <div className="text-sm">
                  <span className="font-medium">{lastResult.admission_number}</span>
                  {lastResult.bed?.bed_number && (
                    <span className="text-muted-foreground">
                      {' '}→ bed {lastResult.bed.bed_number} ({lastResult.bed.type})
                    </span>
                  )}
                </div>
              </div>
              <AgentRationale
                rationale={lastResult.triage.rationale}
                confidence={lastResult.triage.confidence}
                modelVersion={lastResult.triage.model_version}
                usedFallback={lastResult.triage.used_fallback}
                redFlags={lastResult.triage.red_flags}
              />
            </div>
          )}
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>New Arrival</CardTitle>
          </CardHeader>
          <CardContent>
            <ArrivalForm onResult={handleArrival} />
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  )
}
