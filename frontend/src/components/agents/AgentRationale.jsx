import { Bot, ShieldAlert } from 'lucide-react'
import { motion } from 'framer-motion'

import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'

/**
 * Renders an agent's decision with its rationale and confidence. The advisory
 * banner is deliberate: every clinical output is labelled as requiring human
 * confirmation, per the project's ethics posture.
 */
export function AgentRationale({ rationale, confidence, modelVersion, usedFallback, redFlags = [] }) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <Card className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-gradient shadow-glow">
              <Bot className="h-4 w-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold">Patient Triage Agent</p>
              <p className="font-mono text-xs text-muted-foreground">{modelVersion}</p>
            </div>
          </div>
          {confidence != null && (
            <Badge variant={confidence >= 0.75 ? 'success' : 'warning'}>
              {Math.round(confidence * 100)}% confidence
            </Badge>
          )}
        </div>

        {redFlags.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {redFlags.map((flag) => (
              <Badge key={flag} variant="danger">
                <ShieldAlert className="h-3 w-3" /> {flag.replace(/_/g, ' ')}
              </Badge>
            ))}
          </div>
        )}

        <p className="text-sm leading-relaxed text-foreground/90">{rationale}</p>

        <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-xs text-amber-500">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Advisory only. A clinician must confirm before any patient-affecting action.
            {usedFallback && ' Decision produced by the deterministic rule engine.'}
          </span>
        </div>
      </Card>
    </motion.div>
  )
}
