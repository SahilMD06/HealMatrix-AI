import { Hammer } from 'lucide-react'

import { PageContainer } from '@/components/layout/PageContainer'
import { Card, CardContent } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/States'

/**
 * Honest placeholder for dashboards scheduled in a later phase. It states plainly
 * what is coming rather than pretending to be finished — no dummy charts.
 */
export default function PlaceholderDashboard({ title, phase = 'a future release', endpoints = [] }) {
  return (
    <PageContainer title={title} subtitle={`Coming in ${phase}`}>
      <Card>
        <CardContent className="pt-6">
          <EmptyState
            icon={Hammer}
            title={`${title} is coming in ${phase}`}
            description="The underlying data for this view is already available via the API and is listed below. The dedicated visual layer for it isn't built yet."
          />
          {endpoints.length > 0 && (
            <div className="mx-auto mt-4 max-w-md">
              <p className="mb-2 text-center text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Available endpoints
              </p>
              <div className="space-y-1">
                {endpoints.map((e) => (
                  <code
                    key={e}
                    className="block rounded bg-secondary px-3 py-1.5 text-center font-mono text-xs"
                  >
                    {e}
                  </code>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </PageContainer>
  )
}
