import { Hammer } from 'lucide-react'

import { PageContainer } from '@/components/layout/PageContainer'
import { Card, CardContent } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/States'

/**
 * Honest placeholder for dashboards scheduled in a later phase. It states plainly
 * what is coming rather than pretending to be finished — no dummy charts.
 */
export default function PlaceholderDashboard({ title, phase = 'a later phase', endpoints = [] }) {
  return (
    <PageContainer title={title} subtitle={`Scheduled for ${phase}`}>
      <Card>
        <CardContent className="pt-6">
          <EmptyState
            icon={Hammer}
            title={`${title} is coming in ${phase}`}
            description="The backend data for this view already exists and is listed below. The visual layer lands in a later build phase."
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
