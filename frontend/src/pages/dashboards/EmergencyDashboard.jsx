import { Ambulance, BedDouble, Building2, Percent } from 'lucide-react'

import { PageContainer } from '@/components/layout/PageContainer'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { StatCard } from '@/components/ui/StatCard'
import { DonutChart, CategoryBarChart } from '@/components/charts/Charts'
import { ErrorState, Skeleton } from '@/components/ui/States'
import { useApi } from '@/hooks/useApi'

/**
 * Emergency / operations dashboard: live bed occupancy across the hospital, ICU
 * pressure, and per-department load. All figures come from the occupancy endpoint.
 */
export default function EmergencyDashboard() {
  const occupancy = useApi('/beds/occupancy-summary', { pollMs: 15000 })
  const overview = useApi('/analytics/overview', { pollMs: 20000 })

  const o = occupancy.data
  const kpi = overview.data || {}

  const statusDonut = o
    ? [
        { name: 'Occupied', value: o.occupied, color: '#0ea5e9' },
        { name: 'Available', value: o.available, color: '#14b8a6' },
        { name: 'Cleaning', value: o.cleaning, color: '#f59e0b' },
        { name: 'Reserved', value: o.reserved, color: '#8b5cf6' },
        { name: 'Maintenance', value: o.maintenance, color: '#ef4444' },
      ].filter((s) => s.value > 0)
    : []

  const deptBars = (o?.by_department || []).map((d) => ({
    name: d.department || '—',
    Occupied: d.breakdown?.occupied || 0,
    Available: d.breakdown?.available || 0,
  }))

  return (
    <PageContainer title="Emergency & Operations" subtitle="Live bed and capacity picture">
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Building2} label="Total beds" value={o ? o.total_beds : 0} accent="indigo" delay={0} />
        <StatCard icon={BedDouble} label="Available now" value={o ? o.available : 0} accent="emerald" delay={0.05} />
        <StatCard
          icon={Percent}
          label="Occupancy"
          value={o ? o.occupancy_rate : 0}
          unit="%"
          decimals={1}
          accent="cyan"
          delay={0.1}
        />
        <StatCard
          icon={Ambulance}
          label="ICU occupancy"
          value={o ? o.icu_occupancy_rate : 0}
          unit="%"
          decimals={1}
          accent="rose"
          delay={0.15}
          trend={o && o.icu_occupancy_rate >= 90 ? o.icu_occupancy_rate - 90 : null}
          trendLabel="over threshold"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Bed status mix</CardTitle>
          </CardHeader>
          <CardContent>
            {occupancy.loading && !o ? (
              <Skeleton className="h-56 w-full" />
            ) : occupancy.error ? (
              <ErrorState error={occupancy.error} onRetry={occupancy.refetch} />
            ) : (
              <DonutChart data={statusDonut} />
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Occupancy by department</CardTitle>
          </CardHeader>
          <CardContent>
            {occupancy.loading && !o ? (
              <Skeleton className="h-56 w-full" />
            ) : (
              <CategoryBarChart
                data={deptBars}
                xKey="name"
                series={[
                  { key: 'Occupied', label: 'Occupied', color: '#0ea5e9', stack: 'a' },
                  { key: 'Available', label: 'Available', color: '#14b8a6', stack: 'a' },
                ]}
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-6">
        <Card>
          <CardHeader>
            <CardTitle>Live summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 text-sm sm:grid-cols-3">
              <div>
                <p className="text-muted-foreground">Active census</p>
                <p className="mt-1 font-mono text-2xl font-bold">{kpi.census ?? '—'}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Critical patients</p>
                <p className="mt-1 font-mono text-2xl font-bold">{kpi.critical_active ?? '—'}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Admissions (24h)</p>
                <p className="mt-1 font-mono text-2xl font-bold">{kpi.admissions_24h ?? '—'}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  )
}
