import { Bot, CheckCircle2, Clock, Zap } from 'lucide-react'

import { PageContainer } from '@/components/layout/PageContainer'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/States'
import { useApi } from '@/hooks/useApi'
import { formatNumber } from '@/lib/utils'

/** Agent transparency: per-agent health and the most recent reasoning runs. */
export default function AgentsDashboard() {
  const status = useApi('/agents/status', { pollMs: 20000 })
  const runs = useApi('/agents/runs', { pollMs: 20000 })

  return (
    <PageContainer title="AI Agents" subtitle="Health and reasoning trail of the agent network">
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Agent roster</CardTitle>
          </CardHeader>
          <CardContent>
            {status.loading && !status.data ? (
              <div className="space-y-2">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
            ) : status.error ? (
              <ErrorState error={status.error} onRetry={status.refetch} />
            ) : (
              <div className="space-y-2">
                {status.data.map((agent) => (
                  <div
                    key={agent.agent}
                    className="flex items-center gap-3 rounded-md border border-border bg-card px-3 py-2.5"
                  >
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                      <Bot className="h-4 w-4 text-primary" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium capitalize">
                        {agent.agent.replace(/_/g, ' ')}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {agent.runs > 0 ? `${agent.runs} runs · avg ${formatNumber(agent.avg_duration_ms)}ms` : 'No runs yet'}
                      </p>
                    </div>
                    {agent.implemented ? (
                      <Badge variant="success"><CheckCircle2 className="h-3 w-3" /> Active</Badge>
                    ) : (
                      <Badge variant="outline">Phase 3</Badge>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent runs</CardTitle>
          </CardHeader>
          <CardContent>
            {runs.loading && !runs.data ? (
              <div className="space-y-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
            ) : runs.error ? (
              <ErrorState error={runs.error} onRetry={runs.refetch} />
            ) : !runs.data?.length ? (
              <EmptyState icon={Zap} title="No agent runs yet" description="Register a patient arrival to trigger the agent graph." />
            ) : (
              <div className="space-y-2">
                {runs.data.map((run) => (
                  <div key={run.run_id} className="rounded-md border border-border bg-card px-3 py-2.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-muted-foreground">
                        {run.run_id.slice(0, 8)}
                      </span>
                      <div className="flex items-center gap-2">
                        {run.degraded ? (
                          <Badge variant="warning">degraded</Badge>
                        ) : (
                          <Badge variant="success">success</Badge>
                        )}
                        <span className="flex items-center gap-1 text-xs text-muted-foreground">
                          <Clock className="h-3 w-3" /> {run.duration_ms}ms
                        </span>
                      </div>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {run.agents} agents · {run.triggered_by?.replace(/_/g, ' ')}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  )
}
