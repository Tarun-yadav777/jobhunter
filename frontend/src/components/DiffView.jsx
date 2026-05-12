import { useEffect, useRef, useState } from 'react'

// ── Word-level diff highlight ─────────────────────────────────────────────────
// Returns an array of { word, isNew } tokens.
// A tailored word is "new" if it does not appear in the original text
// (case-insensitive, stripped of punctuation, min 4 chars to skip noise).

function diffWords(originalText, tailoredText) {
  const origSet = new Set(
    (originalText || '')
      .toLowerCase()
      .split(/\W+/)
      .filter((w) => w.length >= 4)
  )
  return tailoredText.split(' ').map((word) => {
    const clean = word.toLowerCase().replace(/[^a-z0-9]/g, '')
    const isNew = clean.length >= 4 && !origSet.has(clean)
    return { word, isNew }
  })
}

// Render a tailored bullet with new words highlighted in amber.
function HighlightedBullet({ originalText, bullet }) {
  const tokens = diffWords(originalText, bullet)
  const hasChanges = tokens.some((t) => t.isNew)
  return (
    <span>
      {hasChanges && (
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5 mb-0.5 flex-shrink-0 align-middle" title="Contains new/changed content" />
      )}
      {tokens.map((t, i) =>
        t.isNew ? (
          <mark key={i} className="bg-amber-100 text-amber-900 rounded px-0 not-italic">{t.word} </mark>
        ) : (
          <span key={i}>{t.word} </span>
        )
      )}
    </span>
  )
}

// ── Auto-resize textarea ──────────────────────────────────────────────────────

function AutoTextarea({ value, onChange, onBlur, className }) {
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
      rows={1}
      value={value}
      onChange={onChange}
      onBlur={onBlur}
      className={`resize-none overflow-hidden w-full ${className}`}
    />
  )
}

// ── Single experience row ─────────────────────────────────────────────────────

function ExperienceRow({ orig, tailored, onBulletsChange, onBlur }) {
  // orig = { title, company, start_date, end_date, description } | null
  // tailored = { title, company, dates, bullets: string[] }

  const origText = orig ? (orig.description || '') : ''
  const [bullets, setBullets] = useState(tailored.bullets || [])

  // Propagate local changes up
  useEffect(() => {
    setBullets(tailored.bullets || [])
  }, [tailored.bullets])

  const handleChange = (i, val) => {
    const next = bullets.map((b, idx) => (idx === i ? val : b))
    setBullets(next)
    onBulletsChange(next)
  }

  const handleBlur = () => onBlur()

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gray-50 px-4 py-2.5 border-b border-gray-200">
        <p className="text-sm font-semibold text-gray-900">
          {tailored.title}
          {tailored.company ? <span className="text-gray-500 font-normal"> · {tailored.company}</span> : null}
        </p>
        {tailored.dates && (
          <p className="text-xs text-gray-400 mt-0.5">{tailored.dates}</p>
        )}
      </div>

      {/* Side-by-side */}
      <div className="grid grid-cols-2 divide-x divide-gray-200">
        {/* Left: original */}
        <div className="p-3 bg-gray-50/50">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Original</p>
          {orig ? (
            <p className="text-xs text-gray-500 leading-relaxed whitespace-pre-line">
              {orig.description || <span className="italic">No description in CV</span>}
            </p>
          ) : (
            <p className="text-xs text-gray-400 italic">No matching original experience</p>
          )}
        </div>

        {/* Right: tailored (editable) */}
        <div className="p-3">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
            Tailored
            <span className="ml-2 text-amber-600 font-normal normal-case">
              ● new content highlighted
            </span>
          </p>
          <ul className="space-y-2">
            {bullets.map((bullet, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="mt-2 text-gray-300 text-xs flex-shrink-0">•</span>
                <div className="flex-1 group relative">
                  {/* Read-only highlighted view */}
                  <div className="text-xs text-gray-700 leading-relaxed pointer-events-none select-none absolute inset-0 px-2 py-1.5 group-focus-within:opacity-0 transition-opacity">
                    <HighlightedBullet originalText={origText} bullet={bullet} />
                  </div>
                  {/* Editable textarea (visible on focus) */}
                  <AutoTextarea
                    value={bullet}
                    onChange={(e) => handleChange(i, e.target.value)}
                    onBlur={handleBlur}
                    className="text-xs text-gray-700 leading-relaxed px-2 py-1.5 rounded border border-transparent focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400 bg-transparent focus:bg-white relative z-10 opacity-0 focus:opacity-100 transition-opacity"
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

// ── Main DiffView ─────────────────────────────────────────────────────────────

export default function DiffView({ resume, originalExperiences = [], onResumeChange, onBlur }) {
  // resume = { full_name, contact, summary, experiences, skills, education }
  // originalExperiences = cv_parsed_json.experiences (from profile)

  const [localResume, setLocalResume] = useState(resume)

  useEffect(() => {
    setLocalResume(resume)
  }, [resume])

  if (!resume) return null

  // Match tailored experiences to original by company name (best-effort)
  const findOrig = (tailoredExp) => {
    const needle = (tailoredExp.company || '').toLowerCase().trim()
    return originalExperiences.find(
      (o) => (o.company || '').toLowerCase().trim().includes(needle) ||
              needle.includes((o.company || '').toLowerCase().trim().slice(0, 6))
    ) || null
  }

  const handleBulletsChange = (expIndex, newBullets) => {
    const next = {
      ...localResume,
      experiences: localResume.experiences.map((exp, i) =>
        i === expIndex ? { ...exp, bullets: newBullets } : exp
      ),
    }
    setLocalResume(next)
    onResumeChange(next)
  }

  // Summary edit
  const handleSummaryChange = (val) => {
    const next = { ...localResume, summary: val }
    setLocalResume(next)
    onResumeChange(next)
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
          Professional summary
        </p>
        <AutoTextarea
          value={localResume.summary || ''}
          onChange={(e) => handleSummaryChange(e.target.value)}
          onBlur={onBlur}
          className="input text-sm leading-relaxed"
        />
      </div>

      {/* Experiences */}
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Experience ({localResume.experiences?.length || 0} roles)
        </p>
        <div className="space-y-3">
          {(localResume.experiences || []).map((exp, i) => (
            <ExperienceRow
              key={i}
              orig={findOrig(exp)}
              tailored={exp}
              onBulletsChange={(newBullets) => handleBulletsChange(i, newBullets)}
              onBlur={onBlur}
            />
          ))}
        </div>
      </div>

      {/* Skills (read-only display) */}
      {localResume.skills && (
        <div className="card p-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Skills</p>
          <div className="space-y-1.5">
            {(localResume.skills.technical || []).length > 0 && (
              <div className="flex flex-wrap gap-1">
                <span className="text-xs text-gray-500 mr-1">Technical:</span>
                {localResume.skills.technical.map((s) => (
                  <span key={s} className="badge-gray">{s}</span>
                ))}
              </div>
            )}
            {(localResume.skills.tools || []).length > 0 && (
              <div className="flex flex-wrap gap-1">
                <span className="text-xs text-gray-500 mr-1">Tools:</span>
                {localResume.skills.tools.map((s) => (
                  <span key={s} className="badge-gray">{s}</span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
