import { Award, Droplets, Recycle, Zap } from 'lucide-react'

import { PageContainer } from '@/components/layout/PageContainer'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { StatCard } from '@/components/ui/StatCard'
import { Badge } from '@/components/ui/Badge'
import { AreaTrendChart, DonutChart } from '@/components/charts/Charts'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/States'
import { useApi } from '@/hooks/useApi'

const GRADE_VARIANT = { 'A+': 'success', A: 'success', B: 'primary', C: 'warning', D: 'danger', E: 'danger' }

function hourLabel(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return Number.isNaN(date.getTime())
    ? String(timestamp).slice(11, 16)
    : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/**
 * Sustainability dashboard: energy, water and waste telemetry plus the Carbon
 * Intelligence Agent's deterministic emissions breakdown and composite score.
 * All figures come from /sustainability/*, computed live on every load.
 */
export default function SustainabilityDashboard() {
  const summary = useApi('/sustainability/summary', { pollMs: 30000 })
  const energyHistory = useApi('/sustainability/energy-history')
  const waterHistory = useApi('/sustainability/water-history')

  const s = summary.data
  const carbon = s?.carbon
  const score = carbon?.sustainability_score

  const energySeries = (energyHistory.data || []).map((row) => ({
    label: hourLabel(row.timestamp),
    Grid: row.grid_kwh,
    Solar: row.solar_kwh,
    'Diesel generator': row.dg_kwh,
  }))

  const waterSeries = (waterHistory.data || []).map((row) => ({
    label: hourLabel(row.timestamp),
    'Consumption (L)': row.consumption_litres,
  }))

  const wasteDonut = s
    ? Object.entries(s.waste_by_category_kg || {})
        .filter(([, kg]) => kg > 0)
        .map(([category, kg]) => ({ name: category, value: Math.round(kg * 10) / 10 }))
    : []

  return (
    <PageContainer title="Sustainability Dashboard" subtitle="Energy, water, waste and carbon — updated live">
      {summary.error ? (
        <ErrorState error={summary.error} onRetry={summary.refetch} />
      ) : (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={Award}
              label="Sustainability score"
              value={score ? score.overall : 0}
              unit={score ? `/100 (${score.grade})` : ''}
              accent="emerald"
              delay={0}
            />
            <StatCard
              icon={Zap}
              label="Total emissions"
              value={carbon ? carbon.total_kg : 0}
              unit="kgCO2e"
              decimals={1}
              accent="indigo"
              delay={0.05}
            />
            <StatCard
              icon={Droplets}
              label="Water leak signal"
              value={s ? Math.round((s.water?.max_leak_probability || 0) * 100) : 0}
              unit="%"
              accent="cyan"
              delay={0.1}
            />
            <StatCard
              icon={Recycle}
              label="Recyclables recovered"
              value={s ? s.recyclable_recovered_kg : 0}
              unit="kg"
              decimals={1}
              accent="emerald"
              delay={0.15}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-5">
            <Card className="lg:col-span-3">
              <CardHeader>
                <CardTitle>Energy source mix, trailing week</CardTitle>
              </CardHeader>
              <CardContent>
                {energyHistory.loading && !energyHistory.data ? (
                  <Skeleton className="h-64 w-full" />
                ) : energySeries.length === 0 ? (
                  <EmptyState title="No energy telemetry yet" description="Readings appear once the simulator or a real feed starts logging." />
                ) : (
                  <AreaTrendChart
                    data={energySeries}
                    xKey="label"
                    height={280}
                    series={[
                      { key: 'Grid', label: 'Grid', color: '#0ea5e9' },
                      { key: 'Solar', label: 'Solar', color: '#14b8a6' },
                      { key: 'Diesel generator', label: 'Diesel generator', color: '#ef4444' },
                    ]}
                  />
                )}
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Waste by category (kg)</CardTitle>
              </CardHeader>
              <CardContent>
                {summary.loading && !s ? (
                  <Skeleton className="h-64 w-full" />
                ) : wasteDonut.length === 0 ? (
                  <EmptyState title="No waste records yet" />
                ) : (
                  <DonutChart data={wasteDonut} height={260} />
                )}
              </CardContent>
            </Card>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-5">
            <Card className="lg:col-span-3">
              <CardHeader>
                <CardTitle>Water consumption, trailing week</CardTitle>
              </CardHeader>
              <CardContent>
                {waterHistory.loading && !waterHistory.data ? (
                  <Skeleton className="h-56 w-full" />
                ) : waterSeries.length === 0 ? (
                  <EmptyState title="No water telemetry yet" />
                ) : (
                  <AreaTrendChart
                    data={waterSeries}
                    xKey="label"
                    height={240}
                    series={[{ key: 'Consumption (L)', label: 'Consumption (L)', color: '#0ea5e9' }]}
                  />
                )}
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Reduction opportunities</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {!carbon || carbon.reduction_opportunities?.length === 0 ? (
                  <EmptyState title="No levers flagged this cycle" description="Nothing crossed the agent's threshold for a recommendation." />
                ) : (
                  carbon.reduction_opportunities.map((lever) => (
                    <div key={lever.lever} className="rounded-lg border border-border p-3 text-sm">
                      <div className="mb-1 flex items-center justify-between">
                        <span className="font-medium">{lever.lever.replace(/_/g, ' ')}</span>
                        <Badge variant="success">{lever.tco2e_abated} tCO2e</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">{lever.description}</p>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>

          {carbon && (
            <div className="mt-6">
              <Card>
                <CardHeader>
                  <CardTitle>Scope breakdown</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 text-sm sm:grid-cols-3">
                    <div>
                      <p className="text-muted-foreground">Scope 1 (direct)</p>
                      <p className="mt-1 font-mono text-2xl font-bold">{carbon.scope1.total} kg</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Scope 2 (grid electricity)</p>
                      <p className="mt-1 font-mono text-2xl font-bold">{carbon.scope2.total} kg</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Scope 3 (waste + water)</p>
                      <p className="mt-1 font-mono text-2xl font-bold">{carbon.scope3.total} kg</p>
                    </div>
                  </div>
                  {score && (
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Badge variant={GRADE_VARIANT[score.grade] || 'default'}>Grade {score.grade}</Badge>
                      <Badge variant="outline">Energy {score.energy}</Badge>
                      <Badge variant="outline">Water {score.water}</Badge>
                      <Badge variant="outline">Waste {score.waste}</Badge>
                      <Badge variant="outline">Carbon {score.carbon}</Badge>
                    </div>
                  )}
                  {summary.data?.degraded && (
                    <p className="mt-3 text-xs text-amber-500">
                      This figure used the deterministic floor — sustainability telemetry was incomplete this cycle.
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </PageContainer>
  )
}
