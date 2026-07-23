import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import api from '@/services/api'

const DISEASE_CATEGORIES = [
  'respiratory', 'cardiac', 'trauma', 'infectious', 'gi', 'neuro', 'obstetric', 'other',
]

// A realistic default that produces a clear, high-acuity result for demos.
const DEFAULT_FORM = {
  full_name: '',
  age: 55,
  sex: 'male',
  comorbidities: '',
  chief_complaint: '',
  disease_category: 'cardiac',
  source: 'walk_in',
  heart_rate: 88,
  systolic_bp: 122,
  diastolic_bp: 78,
  spo2: 97,
  temperature_c: 36.8,
  respiratory_rate: 18,
  gcs: 15,
  pain_score: 3,
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  )
}

const inputClass =
  'focus-ring w-full rounded-md border border-input bg-card px-2.5 py-1.5 text-sm'

/** New-arrival intake that posts to /admissions/arrival and surfaces the result. */
export function ArrivalForm({ onResult }) {
  const [form, setForm] = useState(DEFAULT_FORM)
  const [loading, setLoading] = useState(false)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const setNum = (key) => (e) => setForm((f) => ({ ...f, [key]: Number(e.target.value) }))

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    try {
      const payload = {
        patient: {
          full_name: form.full_name || `Synthetic Patient ${Math.floor(Math.random() * 9000 + 1000)}`,
          age: Number(form.age),
          sex: form.sex,
          comorbidities: form.comorbidities
            ? form.comorbidities.split(',').map((s) => s.trim()).filter(Boolean)
            : [],
        },
        source: form.source,
        chief_complaint: form.chief_complaint,
        disease_category: form.disease_category,
        vitals: {
          heart_rate: form.heart_rate,
          systolic_bp: form.systolic_bp,
          diastolic_bp: form.diastolic_bp,
          spo2: form.spo2,
          temperature_c: form.temperature_c,
          respiratory_rate: form.respiratory_rate,
          gcs: form.gcs,
          pain_score: form.pain_score,
        },
      }
      const { data } = await api.post('/admissions/arrival', payload)
      toast.success(`Triaged ESI ${data.triage.esi_level} → ${data.triage.recommended_department_code}`)
      onResult?.(data)
      setForm(DEFAULT_FORM)
    } catch (err) {
      toast.error(err.message || 'Arrival could not be processed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Patient name (optional)">
          <input className={inputClass} value={form.full_name} onChange={set('full_name')} placeholder="Auto-generated" />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Age">
            <input type="number" min="0" max="120" className={inputClass} value={form.age} onChange={setNum('age')} />
          </Field>
          <Field label="Sex">
            <select className={inputClass} value={form.sex} onChange={set('sex')}>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </Field>
        </div>
      </div>

      <Field label="Chief complaint">
        <input
          required
          className={inputClass}
          value={form.chief_complaint}
          onChange={set('chief_complaint')}
          placeholder="e.g. Central chest pain radiating to left arm"
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Category">
          <select className={inputClass} value={form.disease_category} onChange={set('disease_category')}>
            {DISEASE_CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </Field>
        <Field label="Source">
          <select className={inputClass} value={form.source} onChange={set('source')}>
            <option value="walk_in">Walk-in</option>
            <option value="ambulance">Ambulance</option>
            <option value="referral">Referral</option>
          </select>
        </Field>
      </div>

      <div className="rounded-md border border-border p-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Vitals</p>
        <div className="grid grid-cols-4 gap-2">
          <Field label="HR"><input type="number" className={inputClass} value={form.heart_rate} onChange={setNum('heart_rate')} /></Field>
          <Field label="SBP"><input type="number" className={inputClass} value={form.systolic_bp} onChange={setNum('systolic_bp')} /></Field>
          <Field label="DBP"><input type="number" className={inputClass} value={form.diastolic_bp} onChange={setNum('diastolic_bp')} /></Field>
          <Field label="SpO₂"><input type="number" step="0.1" className={inputClass} value={form.spo2} onChange={setNum('spo2')} /></Field>
          <Field label="Temp °C"><input type="number" step="0.1" className={inputClass} value={form.temperature_c} onChange={setNum('temperature_c')} /></Field>
          <Field label="RR"><input type="number" className={inputClass} value={form.respiratory_rate} onChange={setNum('respiratory_rate')} /></Field>
          <Field label="GCS"><input type="number" min="3" max="15" className={inputClass} value={form.gcs} onChange={setNum('gcs')} /></Field>
          <Field label="Pain"><input type="number" min="0" max="10" className={inputClass} value={form.pain_score} onChange={setNum('pain_score')} /></Field>
        </div>
      </div>

      <Button type="submit" className="w-full" loading={loading}>
        {loading ? 'Running triage agent…' : 'Register arrival & run triage'}
      </Button>
    </form>
  )
}
