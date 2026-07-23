import { useState } from 'react'
import { AlertOctagon, ListChecks, PlayCircle, ShieldAlert, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

import { PageContainer } from '@/components/layout/PageContainer'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, ErrorState } from '@/components/ui/States'
import api from '@/services/api'

const SEVERITY_VARIANT = { high: 'danger', medium: 'warning', low: 'default' }
const IMPACT_VARIANT = {
  patient_safety: 'danger',
  regulatory_compliance: 'warning',
  cost: 'primary',
  sustainability: 'success',
}

/**
 * Executive dashboard: the CrewAI-synthesised (or, with no LLM key configured,
 * deterministically ranked — see app/agents/crews/executive_crew.py) action
 * plan and risk register from the full scheduled_cycle agent chain, run
 * on demand via POST /agents/run-cycle rather than waiting for the hourly beat.
 */
export default function ExecutiveDashboard() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [run, setRun] = useState(null)

  async function runCycle() {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.post('/agents/run-cycle')
      setRun(data)
      toast.success(`Cycle complete — ${data.agents_run.length} agents ran`)
    } catch (err) {
      setError(err)
      toast.error(err.message || 'Could not run the agent cycle.')
    } finally {
      setLoading(false)
    }
  }

  const executive = run?.results?.executive_decision
  const output = executive?.output
  const carbon = run?.results?.carbon_intelligence?.output
  const disease = run?.results?.disease_forecast?.output

  return (
    <PageContainer
      title="Executive Dashboard"
      subtitle="Cross-agent synthesis: action plan, risks and conflicts"
      actions={
        <Button size="sm" onClick={runCycle} loading={loading}>
          <PlayCircle className="h-4 w-4" /> {run ? 'Run again' : 'Run cycle now'}
        </Button>
      }
    >
      {error ? (
        <ErrorState error={error} onRetry={runCycle} />
      ) : !run ? (
        <Card>
          <CardContent className="pt-6">
            <EmptyState
              icon={Sparkles}
              title="No synthesis yet this session"
              description="Run the full agent cycle (disease forecast → medicine → energy → water → waste → carbon → executive synthesis) to see the current action plan and risk register."
              action={
                <Button onClick={runCycle} loading={loading}>
                  <PlayCircle className="h-4 w-4" /> Run cycle now
                </Button>
              }
            />
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Executive summary</CardTitle>
              {executive?.used_fallback && (
                <Badge variant="warning">Deterministic ranking — no LLM configured</Badge>
              )}
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed text-foreground/90">{output?.executive_summary}</p>
              {disease?.outbreak_warnings?.length > 0 && (
                <div className="mt-3 flex items-center gap-2 rounded-lg border border-triage-1/20 bg-triage-1/10 px-3 py-2 text-xs text-triage-1">
                  <AlertOctagon className="h-3.5 w-3.5 shrink-0" />
                  Outbreak signal: {disease.outbreak_warnings.length} forecast day(s) exceed baseline.
                </div>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ListChecks className="h-4 w-4" /> Action plan
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(output?.action_plan || []).length === 0 ? (
                  <EmptyState title="No actions this cycle" description="Nothing crossed a threshold requiring executive attention." />
                ) : (
                  output.action_plan.map((item, i) => (
                    <div key={i} className="rounded-lg border border-border p-3 text-sm">
                      <div className="mb-1 flex flex-wrap items-center gap-1.5">
                        <Badge variant={IMPACT_VARIANT[item.impact] || 'default'}>{item.impact?.replace(/_/g, ' ')}</Badge>
                        <Badge variant="outline">{item.horizon?.replace(/_/g, ' ')}</Badge>
                        <span className="text-xs text-muted-foreground">→ {item.owner_role}</span>
                      </div>
                      <p>{item.action}</p>
                      <p className="mt-1 text-xs text-muted-foreground">source: {item.source_agent}</p>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4" /> Risk register
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(output?.risk_register || []).length === 0 ? (
                  <EmptyState title="No risks flagged this cycle" />
                ) : (
                  output.risk_register.map((risk, i) => (
                    <div key={i} className="flex items-start justify-between gap-3 rounded-lg border border-border p-3 text-sm">
                      <div>
                        <p>{risk.risk}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{risk.category?.replace(/_/g, ' ')}</p>
                      </div>
                      <Badge variant={SEVERITY_VARIANT[risk.severity] || 'default'}>{risk.severity}</Badge>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>

          {output?.conflicts_resolved?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Conflicts resolved</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {output.conflicts_resolved.map((conflict, i) => (
                  <div key={i} className="rounded-lg border border-border p-3 text-sm">
                    <p className="font-medium">{conflict.conflict}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{conflict.resolution}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>This cycle at a glance</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 text-sm sm:grid-cols-3">
                <div>
                  <p className="text-muted-foreground">Agents run</p>
                  <p className="mt-1 font-mono text-2xl font-bold">{run.agents_run.length}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Degraded (fallback)</p>
                  <p className="mt-1 font-mono text-2xl font-bold">{run.degraded.length}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Sustainability grade</p>
                  <p className="mt-1 font-mono text-2xl font-bold">
                    {carbon?.sustainability_score?.grade ?? '—'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </PageContainer>
  )
}
