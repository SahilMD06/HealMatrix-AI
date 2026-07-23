import { AlertTriangle, IndianRupee, PackageX, Timer } from 'lucide-react'

import { PageContainer } from '@/components/layout/PageContainer'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { StatCard } from '@/components/ui/StatCard'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/States'
import { useApi } from '@/hooks/useApi'

function rupees(paise) {
  return `₹${((paise || 0) / 100).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

function daysUntil(dateString) {
  if (!dateString) return null
  const diff = new Date(dateString) - new Date()
  return Math.max(Math.ceil(diff / (1000 * 60 * 60 * 24)), 0)
}

/**
 * Inventory dashboard: expiry risk and reorder alerts from the Medicine
 * Intelligence Agent's own data sources (InventoryRepository), exposed today
 * via /analytics/medicine — no new backend surface needed for this view.
 */
export default function InventoryDashboard() {
  const medicine = useApi('/analytics/medicine', { pollMs: 30000 })
  const m = medicine.data

  return (
    <PageContainer title="Inventory Dashboard" subtitle="Expiry risk, reorder alerts and value at risk">
      {medicine.error ? (
        <ErrorState error={medicine.error} onRetry={medicine.refetch} />
      ) : (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard
              icon={Timer}
              label="Batches expiring (90d)"
              value={m ? m.expiring_count : 0}
              accent="rose"
              delay={0}
            />
            <StatCard
              icon={PackageX}
              label="SKUs at/below reorder point"
              value={m ? m.low_stock_count : 0}
              accent="indigo"
              delay={0.05}
            />
            <StatCard
              icon={IndianRupee}
              label="Value at risk"
              value={m ? Math.round((m.value_at_risk_paise || 0) / 100) : 0}
              unit="₹"
              accent="cyan"
              delay={0.1}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Expiring batches</CardTitle>
              </CardHeader>
              <CardContent>
                {medicine.loading && !m ? (
                  <Skeleton className="h-64 w-full" />
                ) : !m?.expiring?.length ? (
                  <EmptyState title="Nothing expiring soon" description="No batches fall within the 90-day alert window." />
                ) : (
                  <div className="space-y-2">
                    {m.expiring.map((row) => {
                      const days = daysUntil(row.expiry_date)
                      return (
                        <div key={row.id} className="flex items-center justify-between rounded-lg border border-border p-3 text-sm">
                          <div>
                            <p className="font-medium">{row.medicine_name || row.sku}</p>
                            <p className="text-xs text-muted-foreground">
                              Batch {row.batch_number} · {row.quantity} units · {rupees(row.unit_cost_paise * row.quantity)}
                            </p>
                          </div>
                          <Badge variant={days !== null && days <= 7 ? 'danger' : days !== null && days <= 30 ? 'warning' : 'default'}>
                            {days !== null ? `${days}d left` : '—'}
                          </Badge>
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Low stock / reorder alerts</CardTitle>
              </CardHeader>
              <CardContent>
                {medicine.loading && !m ? (
                  <Skeleton className="h-64 w-full" />
                ) : !m?.low_stock?.length ? (
                  <EmptyState title="Stock levels look healthy" description="Nothing is at or below its reorder point." />
                ) : (
                  <div className="space-y-2">
                    {m.low_stock.map((row) => (
                      <div key={row.id} className="flex items-center justify-between rounded-lg border border-border p-3 text-sm">
                        <div>
                          <p className="font-medium">{row.medicine_name || row.sku}</p>
                          <p className="text-xs text-muted-foreground">
                            {row.quantity} on hand · reorder at {row.reorder_point}
                          </p>
                        </div>
                        {row.is_critical && (
                          <Badge variant="danger">
                            <AlertTriangle className="h-3 w-3" /> critical
                          </Badge>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </PageContainer>
  )
}
