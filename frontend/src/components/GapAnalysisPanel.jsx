import { useState } from 'react'
import AtsPanel from './AtsPanel.jsx'

// ── Small helpers ─────────────────────────────────────────────────────────────

function SectionHeading({ children }) {
  return (
    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
      {children}
    </p>
  )
}

function MatchScoreBadge({ score }) {
  const color =
    score >= 75 ? 'text-green-700 bg-green-50 border-green-200'
    : score >= 50 ? 'text-yellow-700 bg-yellow-50 border-yellow-200'
    : 'text-red-700 bg-red-50 border-red-200'

  const label =
    score >= 75 ? 'Strong fit'
    : score >= 50 ? 'Moderate fit'
    : 'Weak fit'

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-semibold ${color}`}>
      <span className="text-2xl font-bold">{score}</span>
      <span className="text-xs font-normal opacity-80">/100 · {label}</span>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function GapAnalysisPanel({ gapAnalysis, ats }) {
  const [showReframe, setShowReframe] = useState(false)

  if (!gapAnalysis) return null

  const {
    match_score = 0,
    matched_skills = [],
    soft_gaps = [],
    hard_gaps = [],
    strengths_to_emphasise = [],
    reframe_opportunities = [],
    strategy = '',
    red_flags = [],
  } = gapAnalysis

  return (
    <div className="space-y-5">
      {/* Match score */}
      <div>
        <SectionHeading>Match score</SectionHeading>
        <MatchScoreBadge score={match_score} />
      </div>

      {/* Strategy */}
      {strategy && (
        <div>
          <SectionHeading>Strategy</SectionHeading>
          <p className="text-sm text-gray-700 leading-relaxed">{strategy}</p>
        </div>
      )}

      {/* Strengths */}
      {strengths_to_emphasise.length > 0 && (
        <div>
          <SectionHeading>Strengths to emphasise</SectionHeading>
          <ul className="space-y-1">
            {strengths_to_emphasise.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                <span className="mt-1 w-1.5 h-1.5 rounded-full bg-blue-500 flex-shrink-0" />
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Matched skills */}
      {matched_skills.length > 0 && (
        <div>
          <SectionHeading>Matched skills ({matched_skills.length})</SectionHeading>
          <div className="flex flex-wrap gap-1">
            {matched_skills.map((s) => (
              <span key={s} className="badge-green">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Soft gaps */}
      {soft_gaps.length > 0 && (
        <div>
          <SectionHeading>Soft gaps — reframeable ({soft_gaps.length})</SectionHeading>
          <div className="flex flex-wrap gap-1">
            {soft_gaps.map((s, i) => (
              <span key={i} className="badge-yellow">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Hard gaps */}
      {hard_gaps.length > 0 && (
        <div>
          <SectionHeading>Hard gaps — flag these ({hard_gaps.length})</SectionHeading>
          <div className="flex flex-wrap gap-1">
            {hard_gaps.map((s, i) => (
              <span key={i} className="badge-red">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Reframe opportunities */}
      {reframe_opportunities.length > 0 && (
        <div>
          <button
            onClick={() => setShowReframe((v) => !v)}
            className="flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            <svg className={`w-3.5 h-3.5 transition-transform ${showReframe ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            {showReframe ? 'Hide' : 'Show'} reframe guidance ({reframe_opportunities.length})
          </button>
          {showReframe && (
            <div className="mt-2 space-y-2">
              {reframe_opportunities.map((r, i) => (
                <div key={i} className="rounded-md bg-blue-50 border border-blue-100 p-3 text-xs">
                  <p className="font-semibold text-blue-800 mb-1">{r.gap}</p>
                  <p className="text-blue-700 leading-relaxed">{r.reframe}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Red flags */}
      {red_flags.length > 0 && (
        <div>
          <SectionHeading>Red flags</SectionHeading>
          <div className="space-y-1.5">
            {red_flags.map((f, i) => (
              <div key={i} className="flex items-start gap-2 rounded-md bg-red-50 border border-red-100 px-3 py-2 text-xs text-red-700">
                <svg className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
                </svg>
                {f}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ATS Panel */}
      <div className="pt-3 border-t border-gray-100">
        <SectionHeading>ATS keywords</SectionHeading>
        <AtsPanel ats={ats} />
      </div>
    </div>
  )
}
