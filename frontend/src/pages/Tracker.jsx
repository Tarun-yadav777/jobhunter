import { useCallback, useEffect, useRef, useState } from 'react'
import { downloadResume, getTrackerCoverLetter, getTrackerResume, getTracker } from '../api/client.js'

// ── Small helpers ──────────────────────────────────────────────────────────────

function Spinner({ size = 5 }) {
  return (
    <svg
      className={`w-${size} h-${size} animate-spin text-blue-600`}
      fill="none" viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  )
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

// ── Resume modal content ───────────────────────────────────────────────────────

function ResumeView({ resume }) {
  if (!resume) return null

  const { full_name, contact, summary, experiences = [], skills = {}, education = [] } = resume
  const { technical = [], tools = [] } = skills

  return (
    <div className="space-y-5 text-sm text-gray-800">
      {/* Header */}
      <div className="text-center pb-4 border-b border-gray-200">
        <p className="text-xl font-bold text-gray-900">{full_name}</p>
        {contact && <p className="text-xs text-gray-500 mt-1">{contact}</p>}
      </div>

      {/* Summary */}
      {summary && (
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-1.5">Summary</p>
          <p className="leading-relaxed text-gray-700">{summary}</p>
        </div>
      )}

      {/* Experience */}
      {experiences.length > 0 && (
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-2">Experience</p>
          <div className="space-y-4">
            {experiences.map((exp, i) => (
              <div key={i}>
                <div className="flex items-baseline justify-between gap-2 flex-wrap">
                  <p className="font-semibold text-gray-900">
                    {exp.title}
                    {exp.company ? (
                      <span className="font-normal text-gray-500"> · {exp.company}</span>
                    ) : null}
                  </p>
                  {exp.dates && (
                    <p className="text-xs text-gray-400 flex-shrink-0">{exp.dates}</p>
                  )}
                </div>
                {(exp.bullets || []).length > 0 && (
                  <ul className="mt-1.5 space-y-1 pl-4">
                    {exp.bullets.map((b, j) => (
                      <li key={j} className="flex items-start gap-2 leading-relaxed text-gray-700">
                        <span className="flex-shrink-0 mt-1 text-gray-300 text-xs">•</span>
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Skills */}
      {(technical.length > 0 || tools.length > 0) && (
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-1.5">Skills</p>
          <div className="space-y-1.5">
            {technical.length > 0 && (
              <div className="flex flex-wrap gap-1 items-center">
                <span className="text-xs text-gray-500 mr-1">Technical:</span>
                {technical.map((s) => (
                  <span key={s} className="badge-gray">{s}</span>
                ))}
              </div>
            )}
            {tools.length > 0 && (
              <div className="flex flex-wrap gap-1 items-center">
                <span className="text-xs text-gray-500 mr-1">Tools:</span>
                {tools.map((s) => (
                  <span key={s} className="badge-gray">{s}</span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Education */}
      {education.length > 0 && (
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-1.5">Education</p>
          <div className="space-y-1">
            {education.map((edu, i) => (
              <p key={i} className="text-gray-700">
                <span className="font-medium">{edu.degree}</span>
                {edu.institution ? <span className="text-gray-500"> · {edu.institution}</span> : null}
                {edu.year ? <span className="text-gray-400"> · {edu.year}</span> : null}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Standalone download button ────────────────────────────────────────────────

function DownloadButton({ appId, app }) {
  const [downloading, setDownloading] = useState(false)
  const [dlError, setDlError]         = useState('')

  const handle = async () => {
    setDlError('')
    setDownloading(true)
    try {
      const { data } = await downloadResume(appId)
      const url = URL.createObjectURL(new Blob([data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      }))
      const a = document.createElement('a')
      a.href = url
      a.download = `Resume_${app.role}_${app.company}.docx`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      setDlError('Failed')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="flex flex-col items-end">
      <button
        onClick={handle}
        disabled={downloading}
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium bg-green-50 text-green-700 hover:bg-green-100 disabled:opacity-50 transition-colors"
        title="Download .docx resume"
      >
        {downloading ? (
          <><Spinner size={3} /><span>Downloading…</span></>
        ) : (
          <>
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            .docx
          </>
        )}
      </button>
      {dlError && <p className="text-xs text-red-500 mt-0.5">{dlError}</p>}
    </div>
  )
}

// ── Modal ──────────────────────────────────────────────────────────────────────

function Modal({ title, onClose, children, loading, error, downloadId, downloadLabel }) {
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState('')

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const handleDownload = async () => {
    if (!downloadId) return
    setDownloadError('')
    setDownloading(true)
    try {
      const { data } = await downloadResume(downloadId)
      const url = URL.createObjectURL(new Blob([data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      }))
      const a = document.createElement('a')
      a.href = url
      a.download = downloadLabel || 'Resume.docx'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      setDownloadError('Download failed — please try again.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 flex-shrink-0">
          <h2 className="text-base font-semibold text-gray-900 truncate mr-3">{title}</h2>
          <div className="flex items-center gap-2 flex-shrink-0">
            {downloadId && (
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5"
              >
                {downloading ? (
                  <><Spinner size={3} /><span>Downloading…</span></>
                ) : (
                  <>
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Download .docx
                  </>
                )}
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              aria-label="Close"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="flex items-center justify-center py-12 gap-3 text-gray-500">
              <Spinner /> Loading…
            </div>
          ) : error ? (
            <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : (
            children
          )}
          {downloadError && (
            <p className="mt-3 text-xs text-red-600">{downloadError}</p>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Tracker page ───────────────────────────────────────────────────────────────

export default function Tracker({ activeProfileId }) {
  const [applications, setApplications] = useState([])
  const [total, setTotal]               = useState(0)
  const [loading, setLoading]           = useState(true)
  const [error, setError]               = useState('')
  const [search, setSearch]             = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // Modal state
  const [modal, setModal]               = useState(null)  // null | { type: 'resume'|'cl', app }
  const [modalData, setModalData]       = useState(null)
  const [modalLoading, setModalLoading] = useState(false)
  const [modalError, setModalError]     = useState('')

  const searchTimer = useRef(null)

  // ── Debounce search input ────────────────────────────────────────────────────

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => setDebouncedSearch(search), 300)
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current) }
  }, [search])

  // ── Fetch applications ───────────────────────────────────────────────────────

  const fetchApplications = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = { limit: 50 }
      if (activeProfileId) params.profile_id = activeProfileId
      if (debouncedSearch.trim()) params.search = debouncedSearch.trim()
      const { data } = await getTracker(params)
      setApplications(data.applications || [])
      setTotal(data.total || 0)
    } catch {
      setError('Could not load applications.')
    } finally {
      setLoading(false)
    }
  }, [activeProfileId, debouncedSearch])

  useEffect(() => {
    fetchApplications()
  }, [fetchApplications])

  // ── Modal open helpers ───────────────────────────────────────────────────────

  const openResumeModal = async (app) => {
    setModal({ type: 'resume', app })
    setModalData(null)
    setModalError('')
    setModalLoading(true)
    try {
      const { data } = await getTrackerResume(app.id)
      setModalData(data)
    } catch {
      setModalError('Could not load resume snapshot.')
    } finally {
      setModalLoading(false)
    }
  }

  const openClModal = async (app) => {
    setModal({ type: 'cl', app })
    setModalData(null)
    setModalError('')
    setModalLoading(true)
    try {
      const { data } = await getTrackerCoverLetter(app.id)
      setModalData(data.text || '')
    } catch {
      setModalError('Could not load cover letter snapshot.')
    } finally {
      setModalLoading(false)
    }
  }

  const closeModal = useCallback(() => {
    setModal(null)
    setModalData(null)
    setModalError('')
  }, [])

  // ── Render ───────────────────────────────────────────────────────────────────

  const docxFilename = modal?.type === 'resume' && modal.app
    ? `Resume_${modal.app.role}_${modal.app.company}.docx`
    : 'Resume.docx'

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Application Tracker</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {loading
              ? 'Loading…'
              : `${total} application${total !== 1 ? 's' : ''} logged`}
          </p>
        </div>

        {/* Search bar */}
        <div className="relative">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search company or role…"
            className="input pl-9 pr-8 py-2 w-64 text-sm"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              aria-label="Clear search"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="card overflow-hidden">
          <div className="divide-y divide-gray-100">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="px-5 py-4 flex items-center gap-4 animate-pulse">
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-48" />
                  <div className="h-3 bg-gray-100 rounded w-32" />
                </div>
                <div className="h-3 bg-gray-100 rounded w-20 hidden md:block" />
                <div className="h-3 bg-gray-100 rounded w-24" />
                <div className="flex gap-2">
                  <div className="h-7 w-16 bg-gray-100 rounded" />
                  <div className="h-7 w-24 bg-gray-100 rounded" />
                  <div className="h-7 w-14 bg-gray-100 rounded" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && applications.length === 0 && (
        <div className="card p-12 text-center space-y-3">
          <div className="w-12 h-12 mx-auto rounded-full bg-gray-100 flex items-center justify-center">
            <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <p className="text-gray-500 font-medium">
            {debouncedSearch ? 'No applications match your search' : 'No applications logged yet'}
          </p>
          <p className="text-sm text-gray-400">
            {debouncedSearch
              ? 'Try a different search term'
              : 'Paste a job description and approve a generation to log your first application'}
          </p>
        </div>
      )}

      {/* Applications table */}
      {!loading && applications.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Company
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Role
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide hidden md:table-cell">
                  Location
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Applied
                </th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Documents
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {applications.map((app) => (
                <tr key={app.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3.5">
                    <p className="font-medium text-gray-900">{app.company}</p>
                  </td>
                  <td className="px-4 py-3.5">
                    <p className="text-gray-700">{app.role}</p>
                  </td>
                  <td className="px-4 py-3.5 hidden md:table-cell">
                    <p className="text-gray-500 text-xs">{app.location || '—'}</p>
                  </td>
                  <td className="px-4 py-3.5">
                    <p className="text-gray-500 text-xs whitespace-nowrap">
                      {formatDate(app.applied_at)}
                    </p>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center justify-end gap-2">
                      {/* View resume */}
                      <button
                        onClick={() => openResumeModal(app)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
                        title="View resume"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        Resume
                      </button>

                      {/* View cover letter */}
                      <button
                        onClick={() => openClModal(app)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium bg-purple-50 text-purple-700 hover:bg-purple-100 transition-colors"
                        title="View cover letter"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                        Cover letter
                      </button>

                      {/* Download .docx */}
                      <DownloadButton appId={app.id} app={app} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Row count footer */}
          {total > applications.length && (
            <div className="px-5 py-3 border-t border-gray-100 bg-gray-50">
              <p className="text-xs text-gray-500">
                Showing {applications.length} of {total} applications
              </p>
            </div>
          )}
        </div>
      )}

      {/* Modal */}
      {modal && (
        <Modal
          title={
            modal.type === 'resume'
              ? `Resume — ${modal.app.role} at ${modal.app.company}`
              : `Cover Letter — ${modal.app.role} at ${modal.app.company}`
          }
          onClose={closeModal}
          loading={modalLoading}
          error={modalError}
          downloadId={modal.type === 'resume' ? modal.app.id : null}
          downloadLabel={docxFilename}
        >
          {modal.type === 'resume' && modalData && (
            <ResumeView resume={modalData} />
          )}
          {modal.type === 'cl' && modalData !== null && (
            <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
              {modalData}
            </p>
          )}
        </Modal>
      )}
    </div>
  )
}
