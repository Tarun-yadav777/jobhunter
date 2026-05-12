// AtsPanel — ATS score ring, matched (green) and missing (red) keywords
// Shows a critical flag when score < 70.

function ScoreRing({ score }) {
  // SVG circle: r=28, circumference=2πr≈175.9
  const r = 28
  const circ = 2 * Math.PI * r
  const fill = circ * (1 - score / 100)
  const color = score >= 80 ? '#16a34a' : score >= 60 ? '#d97706' : '#dc2626'

  return (
    <div className="relative w-20 h-20 flex-shrink-0">
      <svg viewBox="0 0 72 72" className="w-20 h-20 -rotate-90">
        {/* track */}
        <circle cx="36" cy="36" r={r} fill="none" stroke="#e5e7eb" strokeWidth="7" />
        {/* filled arc */}
        <circle
          cx="36" cy="36" r={r}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeDasharray={`${circ}`}
          strokeDashoffset={fill}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-bold leading-none" style={{ color }}>{score}</span>
        <span className="text-xs text-gray-400 leading-none mt-0.5">ATS</span>
      </div>
    </div>
  )
}

export default function AtsPanel({ ats }) {
  if (!ats) return null
  const { score, matched = [], missing = [], total_keywords = 0 } = ats
  const critical = score < 70

  return (
    <div className="space-y-3">
      {/* Score + summary row */}
      <div className="flex items-center gap-4">
        <ScoreRing score={score} />
        <div>
          <p className="text-sm font-semibold text-gray-900">
            {score}% ATS match
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            {matched.length} of {total_keywords} keywords found
          </p>
          {critical && (
            <div className="inline-flex items-center gap-1 mt-1.5 px-2 py-0.5 rounded bg-red-100 text-red-700 text-xs font-medium">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
              </svg>
              Low ATS score — add missing keywords
            </div>
          )}
        </div>
      </div>

      {/* Matched keywords */}
      {matched.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
            Matched ({matched.length})
          </p>
          <div className="flex flex-wrap gap-1">
            {matched.map((kw) => (
              <span key={kw} className="badge-green">{kw}</span>
            ))}
          </div>
        </div>
      )}

      {/* Missing keywords */}
      {missing.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
            Missing ({missing.length})
          </p>
          <div className="flex flex-wrap gap-1">
            {missing.map((kw) => (
              <span key={kw} className="badge-red">{kw}</span>
            ))}
          </div>
        </div>
      )}

      {total_keywords === 0 && (
        <p className="text-xs text-gray-400 italic">No ATS keywords extracted from this job.</p>
      )}
    </div>
  )
}
