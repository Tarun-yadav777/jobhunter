import { useEffect, useRef, useState } from 'react'
import {
  activateProfile,
  createProfile,
  deleteProfile,
  getPreferences,
  getProfile,
  getProfileStatus,
  getProfiles,
  patchProfile,
  reembedProfile,
  updatePreferences,
} from '../api/client.js'

// ── Small reusable bits ───────────────────────────────────────────────────────

function Spinner({ size = 'sm' }) {
  const s = size === 'sm' ? 'w-4 h-4' : 'w-6 h-6'
  return (
    <svg className={`${s} animate-spin text-blue-600`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  )
}

function Alert({ type = 'error', children }) {
  const styles = {
    error: 'bg-red-50 border-red-200 text-red-800',
    success: 'bg-green-50 border-green-200 text-green-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800',
  }
  return (
    <div className={`rounded-md border px-4 py-3 text-sm ${styles[type]}`}>{children}</div>
  )
}

function TagInput({ label, value, onChange, placeholder }) {
  const [input, setInput] = useState('')

  const add = () => {
    const v = input.trim()
    if (v && !value.includes(v)) onChange([...value, v])
    setInput('')
  }

  const remove = (item) => onChange(value.filter((x) => x !== item))

  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex gap-2 mb-2">
        <input
          className="input flex-1"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
          placeholder={placeholder || 'Type and press Enter'}
        />
        <button type="button" onClick={add} className="btn-secondary px-3">
          Add
        </button>
      </div>
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((item) => (
            <span key={item} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-xs font-medium">
              {item}
              <button
                type="button"
                onClick={() => remove(item)}
                className="hover:text-blue-600 leading-none"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ── New profile form ──────────────────────────────────────────────────────────

function NewProfileForm({ onCreated }) {
  const [name, setName] = useState('')
  const [file, setFile] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return setError('Name is required')
    if (!file) return setError('Please upload a CV PDF')
    setError('')
    setSubmitting(true)
    try {
      const fd = new FormData()
      fd.append('name', name.trim())
      fd.append('cv_file', file)
      const r = await createProfile(fd)
      onCreated(r.data)
    } catch (err) {
      setError(err.response?.data?.detail?.message || err.response?.data?.detail || 'Failed to create profile')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="label">Profile name</label>
        <input
          className="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. ML Engineer 2025"
        />
      </div>
      <div>
        <label className="label">CV / Resume (PDF)</label>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          className="block w-full text-sm text-gray-600 file:mr-3 file:py-2 file:px-4 file:rounded-md file:border file:border-gray-300 file:text-sm file:bg-white file:text-gray-700 hover:file:bg-gray-50 cursor-pointer"
          onChange={(e) => setFile(e.target.files[0] || null)}
        />
        <p className="mt-1 text-xs text-gray-500">PDF only. Parsing takes ~30–60s via Ollama.</p>
      </div>
      {error && <Alert type="error">{error}</Alert>}
      <button type="submit" className="btn-primary" disabled={submitting}>
        {submitting ? <><Spinner /> <span className="ml-2">Creating…</span></> : 'Create profile'}
      </button>
    </form>
  )
}

// ── Parse status poller ───────────────────────────────────────────────────────

function ParseStatus({ profileId, onReady }) {
  const [status, setStatus] = useState('parsing')

  useEffect(() => {
    if (status === 'ready' || status === 'failed') return
    const id = setInterval(async () => {
      try {
        const r = await getProfileStatus(profileId)
        setStatus(r.data.status)
        if (r.data.status === 'ready') {
          clearInterval(id)
          onReady()
        } else if (r.data.status === 'failed') {
          clearInterval(id)
        }
      } catch {
        clearInterval(id)
      }
    }, 2000)
    return () => clearInterval(id)
  }, [profileId, status, onReady])

  if (status === 'parsing') {
    return (
      <Alert type="info">
        <div className="flex items-center gap-2">
          <Spinner />
          <span>Parsing CV with Ollama… this takes 30–60 seconds.</span>
        </div>
      </Alert>
    )
  }
  if (status === 'failed') {
    return <Alert type="error">CV parsing failed. Try re-uploading or check server logs.</Alert>
  }
  return <Alert type="success">CV parsed successfully.</Alert>
}

// ── Preferences form ──────────────────────────────────────────────────────────

const DEFAULTS = {
  target_roles: [],
  target_locations: [],
  remote_preference: 'any',
  salary_min_eur: '',
  company_size_pref: 'any',
  industries_to_avoid: [],
  skills_to_grow: [],
  tone_preference: 'professional',
  cover_letter_length: 'medium',
  seniority_target: 'senior',
  notice_period_weeks: 4,
  open_to_contract: false,
  extra_context: '',
}

function PreferencesForm({ profileId }) {
  const [prefs, setPrefs] = useState(DEFAULTS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    getPreferences(profileId)
      .then((r) => {
        const d = r.data
        setPrefs({
          target_roles: d.target_roles || [],
          target_locations: d.target_locations || [],
          remote_preference: d.remote_preference || 'any',
          salary_min_eur: d.salary_min_eur ?? '',
          company_size_pref: d.company_size_pref || 'any',
          industries_to_avoid: d.industries_to_avoid || [],
          skills_to_grow: d.skills_to_grow || [],
          tone_preference: d.tone_preference || 'professional',
          cover_letter_length: d.cover_letter_length || 'medium',
          seniority_target: d.seniority_target || 'senior',
          notice_period_weeks: d.notice_period_weeks ?? 4,
          open_to_contract: d.open_to_contract || false,
          extra_context: d.extra_context || '',
        })
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [profileId])

  const set = (key, val) => setPrefs((p) => ({ ...p, [key]: val }))

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      await updatePreferences(profileId, {
        ...prefs,
        salary_min_eur: prefs.salary_min_eur === '' ? null : Number(prefs.salary_min_eur),
        notice_period_weeks: Number(prefs.notice_period_weeks),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      setError(err.response?.data?.detail?.message || 'Failed to save preferences')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="flex items-center gap-2 text-sm text-gray-500"><Spinner />Loading preferences…</div>

  return (
    <form onSubmit={handleSave} className="space-y-6">
      {/* Targeting */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Targeting</h3>
        <TagInput
          label="Target roles"
          value={prefs.target_roles}
          onChange={(v) => set('target_roles', v)}
          placeholder="e.g. Senior ML Engineer"
        />
        <TagInput
          label="Target locations"
          value={prefs.target_locations}
          onChange={(v) => set('target_locations', v)}
          placeholder="e.g. London, Remote"
        />
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Remote preference</label>
            <select className="input" value={prefs.remote_preference} onChange={(e) => set('remote_preference', e.target.value)}>
              <option value="any">Any</option>
              <option value="remote">Remote only</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On-site only</option>
            </select>
          </div>
          <div>
            <label className="label">Seniority target</label>
            <select className="input" value={prefs.seniority_target} onChange={(e) => set('seniority_target', e.target.value)}>
              <option value="entry">Entry</option>
              <option value="mid">Mid</option>
              <option value="senior">Senior</option>
              <option value="lead">Lead</option>
              <option value="staff">Staff</option>
            </select>
          </div>
          <div>
            <label className="label">Company size</label>
            <select className="input" value={prefs.company_size_pref} onChange={(e) => set('company_size_pref', e.target.value)}>
              <option value="any">Any</option>
              <option value="startup">Startup</option>
              <option value="mid">Mid-size</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>
          <div>
            <label className="label">Min salary (EUR)</label>
            <input
              type="number"
              className="input"
              value={prefs.salary_min_eur}
              onChange={(e) => set('salary_min_eur', e.target.value)}
              placeholder="e.g. 80000"
              min="0"
            />
          </div>
        </div>
        <TagInput
          label="Industries to avoid"
          value={prefs.industries_to_avoid}
          onChange={(v) => set('industries_to_avoid', v)}
          placeholder="e.g. Gambling, Defence"
        />
      </div>

      {/* Generation */}
      <div className="space-y-4 pt-2 border-t border-gray-100">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Generation</h3>
        <TagInput
          label="Skills to grow into"
          value={prefs.skills_to_grow}
          onChange={(v) => set('skills_to_grow', v)}
          placeholder="e.g. MLOps, Kubernetes"
        />
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Cover letter tone</label>
            <select className="input" value={prefs.tone_preference} onChange={(e) => set('tone_preference', e.target.value)}>
              <option value="professional">Professional</option>
              <option value="conversational">Conversational</option>
              <option value="direct">Direct</option>
            </select>
          </div>
          <div>
            <label className="label">Cover letter length</label>
            <select className="input" value={prefs.cover_letter_length} onChange={(e) => set('cover_letter_length', e.target.value)}>
              <option value="short">Short (3 paragraphs)</option>
              <option value="medium">Medium (4 paragraphs)</option>
              <option value="long">Long (5 paragraphs)</option>
            </select>
          </div>
        </div>
        <div>
          <label className="label">Extra context for AI</label>
          <textarea
            className="input resize-none"
            rows={3}
            value={prefs.extra_context}
            onChange={(e) => set('extra_context', e.target.value)}
            placeholder="Anything the AI should know: career goals, constraints, highlights…"
          />
        </div>
      </div>

      {/* Work preferences */}
      <div className="space-y-4 pt-2 border-t border-gray-100">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Work preferences</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Notice period (weeks)</label>
            <input
              type="number"
              className="input"
              value={prefs.notice_period_weeks}
              onChange={(e) => set('notice_period_weeks', e.target.value)}
              min="0"
              max="52"
            />
          </div>
          <div className="flex items-center gap-3 pt-6">
            <input
              type="checkbox"
              id="open_to_contract"
              checked={prefs.open_to_contract}
              onChange={(e) => set('open_to_contract', e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="open_to_contract" className="text-sm text-gray-700">Open to contract roles</label>
          </div>
        </div>
      </div>

      {error && <Alert type="error">{error}</Alert>}
      {saved && <Alert type="success">Preferences saved.</Alert>}

      <button type="submit" className="btn-primary" disabled={saving}>
        {saving ? <><Spinner /><span className="ml-2">Saving…</span></> : 'Save preferences'}
      </button>
    </form>
  )
}

// ── Profile detail panel ──────────────────────────────────────────────────────

function ProfileDetail({ profile, isActive, onActivate, onDeleted, onReembed }) {
  const [showPrefs, setShowPrefs] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [parseStatus, setParseStatus] = useState(null)
  const [reembedStatus, setReembedStatus] = useState('')

  const handleDelete = async () => {
    if (!window.confirm(`Delete profile "${profile.name}"? This cannot be undone.`)) return
    setDeleting(true)
    try {
      await deleteProfile(profile.id)
      onDeleted(profile.id)
    } catch {
      setDeleting(false)
    }
  }

  const handleReembed = async () => {
    setReembedStatus('running')
    try {
      await reembedProfile(profile.id)
      setReembedStatus('done')
      setTimeout(() => setReembedStatus(''), 3000)
      if (onReembed) onReembed()
    } catch {
      setReembedStatus('failed')
    }
  }

  const cvReady = profile.cv_parsed_json && profile.cv_parsed_json !== '{}'

  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900">{profile.name}</h3>
            {isActive && <span className="badge-green">active</span>}
          </div>
          <p className="text-xs text-gray-500 mt-0.5">
            {profile.cv_filename} · Created {new Date(profile.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {!isActive && (
            <button onClick={() => onActivate(profile.id)} className="btn-secondary text-xs py-1 px-2">
              Set active
            </button>
          )}
          <button onClick={handleReembed} disabled={!cvReady || reembedStatus === 'running'} className="btn-secondary text-xs py-1 px-2">
            {reembedStatus === 'running' ? 'Re-embedding…' : reembedStatus === 'done' ? 'Done' : 'Re-embed'}
          </button>
          <button onClick={handleDelete} disabled={deleting} className="btn-danger text-xs py-1 px-2">
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>

      {/* CV status */}
      {!cvReady && <ParseStatus profileId={profile.id} onReady={() => setParseStatus('ready')} />}
      {parseStatus === 'ready' && <Alert type="success">CV is now parsed and ready.</Alert>}
      {reembedStatus === 'failed' && <Alert type="error">Re-embedding failed.</Alert>}

      {/* Parsed CV summary */}
      {cvReady && (
        <div className="text-xs text-gray-500 bg-gray-50 rounded p-2 font-mono truncate">
          CV parsed · {profile.cv_parsed_json.length} chars JSON
        </div>
      )}

      {/* Preferences toggle */}
      <button
        onClick={() => setShowPrefs((s) => !s)}
        className="text-sm text-blue-600 hover:text-blue-800 font-medium"
      >
        {showPrefs ? '▾ Hide preferences' : '▸ Edit preferences'}
      </button>

      {showPrefs && (
        <div className="pt-2 border-t border-gray-100">
          <PreferencesForm profileId={profile.id} />
        </div>
      )}
    </div>
  )
}

// ── Main Profile page ─────────────────────────────────────────────────────────

export default function Profile({ activeProfileId, onProfileChange }) {
  const [profiles, setProfiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [showNew, setShowNew] = useState(false)
  const [parsingId, setParsingId] = useState(null)

  const loadProfiles = () => {
    setLoading(true)
    getProfiles()
      .then((r) => setProfiles(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadProfiles() }, [])

  const handleCreated = (newProfile) => {
    setProfiles((prev) => [newProfile, ...prev])
    setParsingId(newProfile.id)
    setShowNew(false)
  }

  const handleActivate = async (id) => {
    try {
      await activateProfile(id)
      onProfileChange(id)
      setProfiles((prev) => prev.map((p) => ({ ...p, is_active: p.id === id })))
    } catch {}
  }

  const handleDeleted = (id) => {
    setProfiles((prev) => prev.filter((p) => p.id !== id))
    if (id === activeProfileId) onProfileChange(null)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Profiles</h1>
          <p className="text-sm text-gray-500 mt-1">Upload your CV and configure generation preferences.</p>
        </div>
        <button
          onClick={() => setShowNew((s) => !s)}
          className="btn-primary"
        >
          {showNew ? 'Cancel' : '+ New profile'}
        </button>
      </div>

      {showNew && (
        <div className="card p-5">
          <h2 className="section-title">Create new profile</h2>
          <NewProfileForm onCreated={handleCreated} />
        </div>
      )}

      {parsingId && !showNew && (
        <div className="card p-4">
          <ParseStatus profileId={parsingId} onReady={() => { setParsingId(null); loadProfiles() }} />
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-gray-500 text-sm py-8 justify-center">
          <Spinner size="sm" /> Loading profiles…
        </div>
      ) : profiles.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-gray-500 text-sm">No profiles yet. Create one to get started.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {profiles.map((p) => (
            <ProfileDetail
              key={p.id}
              profile={p}
              isActive={p.id === activeProfileId || p.is_active}
              onActivate={handleActivate}
              onDeleted={handleDeleted}
              onReembed={loadProfiles}
            />
          ))}
        </div>
      )}
    </div>
  )
}
