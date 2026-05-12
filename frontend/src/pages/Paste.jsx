import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getGenerationStatus, pasteJob, startGeneration } from '../api/client.js'

// ── Progress step config ──────────────────────────────────────────────────────

const STEPS = [
  { key: 'rag',          label: 'Matching CV to role',              desc: 'Retrieving your most relevant experience…' },
  { key: 'gap_analysis', label: 'Analysing fit',                    desc: 'Identifying gaps, strengths, and strategy…' },
  { key: 'resume',       label: 'Tailoring resume & cover letter',  desc: 'Writing ATS-optimised bullets and cover letter concurrently…' },
]

function stepIndex(step) {
  const i = STEPS.findIndex((s) => s.key === step)
  return i === -1 ? 0 : i
}

function ProgressBar({ step }) {
  const current = stepIndex(step)
  return (
    <div className="space-y-4">
      {STEPS.map((s, i) => {
        const done    = i < current
        const active  = i === current
        const pending = i > current
        return (
          <div key={s.key} className="flex items-start gap-3">
            {/* circle */}
            <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold mt-0.5 ${
              done    ? 'bg-green-500 text-white'
              : active ? 'bg-blue-600 text-white animate-pulse'
              : 'bg-gray-200 text-gray-500'
            }`}>
              {done ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              ) : i + 1}
            </div>
            {/* text */}
            <div className={pending ? 'opacity-40' : ''}>
              <p className={`text-sm font-medium ${active ? 'text-blue-700' : done ? 'text-green-700' : 'text-gray-500'}`}>
                {s.label}
              </p>
              {active && <p className="text-xs text-gray-500 mt-0.5">{s.desc}</p>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Main Paste page ───────────────────────────────────────────────────────────

export default function Paste({ activeProfileId }) {
  const navigate = useNavigate()

  const [text, setText]                 = useState('')
  const [stage, setStage]               = useState('idle')   // idle | parsing | generating | failed
  const [error, setError]               = useState('')
  const [jobInfo, setJobInfo]           = useState(null)      // from POST /jobs/paste
  const [genStep, setGenStep]           = useState('rag')     // current backend step
  const [duplicateJobId, setDuplicateJobId] = useState(null)

  const pollRef = useRef(null)

  // Clean up poll on unmount
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  // ── Helpers ─────────────────────────────────────────────────────────────────

  const stopPoll = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }

  const startPoll = (generationId) => {
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await getGenerationStatus(generationId)
        if (data.step) setGenStep(data.step)
        if (data.status === 'ready') {
          stopPoll()
          navigate(`/review/${generationId}`)
        } else if (data.status === 'failed') {
          stopPoll()
          setError(data.error || 'Generation failed — check server logs.')
          setStage('failed')
        }
      } catch {
        // network hiccup — keep polling
      }
    }, 2000)
  }

  const triggerGeneration = async (jobId) => {
    setStage('generating')
    setGenStep('rag')
    try {
      const { data } = await startGeneration({ job_id: jobId, profile_id: activeProfileId })
      startPoll(data.generation_id)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (detail?.error === 'already_running') {
        setError('Generation already running for this job. Navigating there…')
        // Can't easily recover generation_id here — show friendly message
        setStage('failed')
      } else {
        setError(detail?.message || 'Failed to start generation.')
        setStage('failed')
      }
    }
  }

  // ── Submit flow ──────────────────────────────────────────────────────────────

  const handleSubmit = async (e) => {
    e?.preventDefault()
    if (!text.trim()) return setError('Paste a job description first.')
    if (!activeProfileId) return setError('Select an active profile first.')
    setError('')
    setDuplicateJobId(null)
    setStage('parsing')

    try {
      const { data } = await pasteJob({ text: text.trim(), profile_id: activeProfileId })
      setJobInfo(data)
      await triggerGeneration(data.job_id)
    } catch (err) {
      const detail = err.response?.data?.detail
      const status = err.response?.status

      if (status === 409 && detail?.error === 'duplicate') {
        // Already in DB — offer to re-generate
        setDuplicateJobId(detail.job_id)
        setStage('idle')
      } else if (status === 422) {
        setError(detail?.message || 'Job description is too short or too long.')
        setStage('idle')
      } else {
        setError(detail?.message || 'Failed to parse job description.')
        setStage('idle')
      }
    }
  }

  const handleGenerateDuplicate = () => {
    if (duplicateJobId) {
      setDuplicateJobId(null)
      triggerGeneration(duplicateJobId)
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  const busy = stage === 'parsing' || stage === 'generating'

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Paste Job Description</h1>
        <p className="text-sm text-gray-500 mt-1">
          Paste a full JD — the AI will tailor your resume and write a cover letter.
        </p>
      </div>

      {/* No profile warning */}
      {!activeProfileId && (
        <div className="card p-4 bg-yellow-50 border-yellow-200">
          <p className="text-sm text-yellow-800">
            No active profile. Go to{' '}
            <a href="/profile" className="font-medium underline">Profiles</a> to create or activate one.
          </p>
        </div>
      )}

      {/* Duplicate notice */}
      {duplicateJobId && (
        <div className="card p-4 bg-blue-50 border-blue-200">
          <p className="text-sm text-blue-800 font-medium mb-2">This job is already in your database.</p>
          <p className="text-xs text-blue-700 mb-3">
            Generate a fresh tailored application against the existing job record?
          </p>
          <div className="flex gap-2">
            <button onClick={handleGenerateDuplicate} className="btn-primary text-xs py-1.5">
              Yes, generate fresh
            </button>
            <button onClick={() => setDuplicateJobId(null)} className="btn-secondary text-xs py-1.5">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Main form */}
      {!busy && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Job description</label>
            <textarea
              className="input resize-none font-mono text-xs leading-relaxed"
              rows={18}
              value={text}
              onChange={(e) => { setText(e.target.value); setError('') }}
              placeholder="Paste the full job description here…"
              disabled={busy}
            />
            <p className="mt-1 text-xs text-gray-400">
              {text.length > 0 ? `${text.length} characters` : 'Minimum ~300 characters recommended'}
            </p>
          </div>

          {error && (
            <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!text.trim() || !activeProfileId}
            className="btn-primary w-full py-2.5 text-base"
          >
            Parse &amp; Generate →
          </button>
        </form>
      )}

      {/* Progress display */}
      {busy && (
        <div className="card p-6 space-y-6">
          <div>
            <h2 className="text-base font-semibold text-gray-900 mb-1">
              {stage === 'parsing' ? 'Parsing job description…' : 'Generating your application…'}
            </h2>
            {jobInfo && (
              <p className="text-sm text-gray-500">
                {jobInfo.title} at {jobInfo.company}
                {jobInfo.location ? ` · ${jobInfo.location}` : ''}
              </p>
            )}
          </div>

          {stage === 'parsing' && (
            <div className="flex items-center gap-3 text-sm text-gray-600">
              <svg className="w-5 h-5 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
              </svg>
              Extracting structured data from JD…
            </div>
          )}

          {stage === 'generating' && <ProgressBar step={genStep} />}

          <p className="text-xs text-gray-400">
            Ollama runs locally — this takes 2–10 minutes depending on model speed.
          </p>
        </div>
      )}

      {/* Failed state */}
      {stage === 'failed' && (
        <div className="card p-6 space-y-4">
          <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
          <button onClick={() => { setStage('idle'); setError('') }} className="btn-secondary">
            Try again
          </button>
        </div>
      )}
    </div>
  )
}
