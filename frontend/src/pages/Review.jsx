import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  approveGeneration,
  getGeneration,
  getProfile,
  patchCoverLetter,
  patchResume,
} from '../api/client.js'
import DiffView from '../components/DiffView.jsx'
import GapAnalysisPanel from '../components/GapAnalysisPanel.jsx'

// ── Small helpers ─────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg className="w-5 h-5 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
    </svg>
  )
}

function SaveIndicator({ state }) {
  if (state === 'saving') return (
    <span className="flex items-center gap-1 text-xs text-gray-400">
      <Spinner /> Saving…
    </span>
  )
  if (state === 'saved') return (
    <span className="text-xs text-green-600 font-medium">✓ Saved</span>
  )
  if (state === 'error') return (
    <span className="text-xs text-red-600">Save failed</span>
  )
  return null
}

// ── Auto-resize textarea (cover letter) ──────────────────────────────────────

function AutoTextarea({ value, onChange, onBlur, rows = 6, className = '' }) {
  const ref = useRef(null)
  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = 'auto'
      ref.current.style.height = ref.current.scrollHeight + 'px'
    }
  }, [value])
  return (
    <textarea
      ref={ref}
      rows={rows}
      value={value}
      onChange={onChange}
      onBlur={onBlur}
      className={`input resize-none overflow-hidden text-sm leading-relaxed ${className}`}
    />
  )
}

// ── Review page ───────────────────────────────────────────────────────────────

export default function Review({ activeProfileId }) {
  const { generationId } = useParams()
  const navigate = useNavigate()

  // Data
  const [generation, setGeneration]           = useState(null)
  const [originalExps, setOriginalExps]       = useState([])
  const [loading, setLoading]                 = useState(true)
  const [loadError, setLoadError]             = useState('')

  // Local edits — ref mirrors state to avoid stale closure in blur handlers
  const [resumeData, setResumeData]           = useState(null)
  const resumeDataRef                         = useRef(null)
  const [coverLetter, setCoverLetter]         = useState('')
  const coverLetterRef                        = useRef('')

  // Save state indicators
  const [resumeSave, setResumeSave]           = useState('')  // '' | 'saving' | 'saved' | 'error'
  const [clSave, setClSave]                   = useState('')

  // Approve
  const [approving, setApproving]             = useState(false)
  const [approveError, setApproveError]       = useState('')

  // Debounce timers
  const resumeTimer = useRef(null)
  const clTimer     = useRef(null)

  // ── Load generation + original profile ─────────────────────────────────────

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError('')

    getGeneration(generationId)
      .then(({ data }) => {
        if (cancelled) return
        setGeneration(data)
        setResumeData(data.resume)
        resumeDataRef.current = data.resume
        setCoverLetter(data.cover_letter)
        coverLetterRef.current = data.cover_letter
      })
      .catch((err) => {
        if (cancelled) return
        const detail = err.response?.data?.detail
        setLoadError(detail?.message || 'Could not load generation.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [generationId])

  // Load original CV experiences for DiffView
  useEffect(() => {
    if (!activeProfileId) return
    getProfile(activeProfileId)
      .then(({ data }) => {
        try {
          const cv = JSON.parse(data.cv_parsed_json || '{}')
          setOriginalExps(cv.experiences || [])
        } catch {
          setOriginalExps([])
        }
      })
      .catch(() => {})
  }, [activeProfileId])

  // Cleanup timers
  useEffect(() => () => {
    if (resumeTimer.current) clearTimeout(resumeTimer.current)
    if (clTimer.current) clearTimeout(clTimer.current)
  }, [])

  // ── Debounced save — resume ─────────────────────────────────────────────────

  const scheduleResumeSave = useCallback((data) => {
    if (resumeTimer.current) clearTimeout(resumeTimer.current)
    resumeTimer.current = setTimeout(async () => {
      setResumeSave('saving')
      try {
        await patchResume(generationId, { resume_edited_json: data })
        setResumeSave('saved')
        setTimeout(() => setResumeSave(''), 2000)
      } catch {
        setResumeSave('error')
      }
    }, 1000)
  }, [generationId])

  // ── Debounced save — cover letter ───────────────────────────────────────────

  const scheduleClSave = useCallback((text) => {
    if (clTimer.current) clearTimeout(clTimer.current)
    clTimer.current = setTimeout(async () => {
      setClSave('saving')
      try {
        await patchCoverLetter(generationId, { cover_letter_edited: text })
        setClSave('saved')
        setTimeout(() => setClSave(''), 2000)
      } catch {
        setClSave('error')
      }
    }, 1000)
  }, [generationId])

  const handleResumeChange = (updated) => {
    setResumeData(updated)
    resumeDataRef.current = updated
  }

  const handleResumeBlur = () => {
    const data = resumeDataRef.current || resumeData
    if (data) scheduleResumeSave(data)
  }

  const handleClChange = (e) => {
    setCoverLetter(e.target.value)
    coverLetterRef.current = e.target.value
  }

  const handleClBlur = () => {
    scheduleClSave(coverLetterRef.current !== '' ? coverLetterRef.current : coverLetter)
  }

  // ── Approve ─────────────────────────────────────────────────────────────────

  const handleApprove = async () => {
    setApproveError('')
    setApproving(true)
    // Flush any pending saves first
    if (resumeTimer.current) { clearTimeout(resumeTimer.current); resumeTimer.current = null }
    if (clTimer.current)     { clearTimeout(clTimer.current);     clTimer.current = null }
    try {
      // Save latest edits immediately before approving (use refs to avoid stale closures)
      const latestResume = resumeDataRef.current || resumeData
      const latestCl = coverLetterRef.current !== '' ? coverLetterRef.current : coverLetter
      if (latestResume) await patchResume(generationId, { resume_edited_json: latestResume })
      await patchCoverLetter(generationId, { cover_letter_edited: latestCl })
      await approveGeneration(generationId)
      navigate('/tracker')
    } catch (err) {
      const detail = err.response?.data?.detail
      if (detail?.error === 'already_approved') {
        navigate('/tracker')
      } else {
        setApproveError(detail?.message || 'Approval failed.')
        setApproving(false)
      }
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 gap-3 text-gray-500">
        <Spinner /> Loading generation…
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="max-w-lg mx-auto mt-12 card p-6 text-center space-y-3">
        <p className="text-red-600 font-medium">{loadError}</p>
        <button onClick={() => navigate('/paste')} className="btn-secondary">
          Back to Paste
        </button>
      </div>
    )
  }

  const { gap_analysis, ats, job_id } = generation

  return (
    <div className="space-y-0">
      {/* ── Top bar ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-5 gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Review Application</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Edit any section — changes auto-save on blur. Click the bullet text to edit.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/paste')} className="btn-secondary text-sm py-2">
            ← New JD
          </button>
          <button
            onClick={handleApprove}
            disabled={approving}
            className="btn-primary text-sm py-2 px-5"
          >
            {approving ? (
              <><Spinner /><span className="ml-2">Approving…</span></>
            ) : (
              '✓ Approve & log application'
            )}
          </button>
        </div>
      </div>

      {approveError && (
        <div className="mb-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {approveError}
        </div>
      )}

      {/* ── Two-column layout ─────────────────────────────────────────────── */}
      <div className="flex gap-5 items-start">

        {/* Left: gap analysis sidebar */}
        <div className="w-72 flex-shrink-0 card p-4 sticky top-[4.5rem]" style={{ maxHeight: 'calc(100vh - 5.5rem)', overflowY: 'auto' }}>
          <h2 className="text-sm font-bold text-gray-900 mb-4">Fit Analysis</h2>
          <GapAnalysisPanel gapAnalysis={gap_analysis} ats={ats} />
        </div>

        {/* Right: resume + cover letter */}
        <div className="flex-1 min-w-0 space-y-6">

          {/* Resume section */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-gray-900">Tailored Resume</h2>
              <SaveIndicator state={resumeSave} />
            </div>
            {resumeData && (
              <DiffView
                resume={resumeData}
                originalExperiences={originalExps}
                onResumeChange={handleResumeChange}
                onBlur={handleResumeBlur}
              />
            )}
          </div>

          {/* Cover letter section */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-bold text-gray-900">Cover Letter</h2>
              <SaveIndicator state={clSave} />
            </div>
            <p className="text-xs text-gray-400 mb-3">
              Click to edit · Changes save automatically on blur
            </p>
            <AutoTextarea
              value={coverLetter}
              onChange={handleClChange}
              onBlur={handleClBlur}
              rows={12}
            />
          </div>

          {/* Bottom approve */}
          <div className="card p-4 bg-green-50 border-green-200 flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-green-800">Ready to apply?</p>
              <p className="text-xs text-green-700 mt-0.5">
                This will save a snapshot and log the application in your tracker.
              </p>
            </div>
            <button
              onClick={handleApprove}
              disabled={approving}
              className="btn-primary text-sm flex-shrink-0"
            >
              {approving ? 'Approving…' : '✓ Approve & log'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
