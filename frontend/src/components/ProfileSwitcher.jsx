import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { activateProfile, getProfiles } from '../api/client.js'

export default function ProfileSwitcher({ activeProfileId, onProfileChange }) {
  const [profiles, setProfiles] = useState([])
  const [open, setOpen] = useState(false)
  const [switching, setSwitching] = useState(false)
  const dropdownRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    getProfiles()
      .then((r) => setProfiles(r.data))
      .catch(() => {})
  }, [activeProfileId])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const active = profiles.find((p) => p.id === activeProfileId)

  const handleActivate = async (profileId) => {
    if (profileId === activeProfileId || switching) return
    setSwitching(true)
    setOpen(false)
    try {
      await activateProfile(profileId)
      onProfileChange(profileId)
    } catch (e) {
      console.error('Failed to switch profile', e)
    } finally {
      setSwitching(false)
    }
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm border border-gray-300 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
        disabled={switching}
      >
        <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
        <span className="max-w-[180px] truncate text-gray-700">
          {switching ? 'Switching…' : active ? active.name : 'No active profile'}
        </span>
        <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1">
          {profiles.length === 0 ? (
            <p className="px-4 py-2 text-sm text-gray-500">No profiles yet</p>
          ) : (
            profiles.map((p) => (
              <button
                key={p.id}
                onClick={() => handleActivate(p.id)}
                className={`w-full text-left px-4 py-2 text-sm flex items-center gap-2 hover:bg-gray-50 ${
                  p.id === activeProfileId ? 'font-medium text-blue-700' : 'text-gray-700'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    p.id === activeProfileId ? 'bg-green-500' : 'bg-gray-300'
                  }`}
                />
                <span className="truncate">{p.name}</span>
                {p.id === activeProfileId && (
                  <span className="ml-auto text-xs text-blue-600">active</span>
                )}
              </button>
            ))
          )}
          <div className="border-t border-gray-100 mt-1 pt-1">
            <button
              onClick={() => { setOpen(false); navigate('/profile') }}
              className="w-full text-left px-4 py-2 text-sm text-blue-600 hover:bg-gray-50"
            >
              + Manage profiles
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
