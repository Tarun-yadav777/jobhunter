import { useEffect, useState } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import { getSettings } from './api/client.js'
import ProfileSwitcher from './components/ProfileSwitcher.jsx'
import Paste from './pages/Paste.jsx'
import Profile from './pages/Profile.jsx'
import Review from './pages/Review.jsx'
import Tracker from './pages/Tracker.jsx'

function NavLink({ to, children }) {
  const location = useLocation()
  const active = location.pathname === to || location.pathname.startsWith(to + '/')
  return (
    <Link
      to={to}
      className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
        active
          ? 'bg-blue-50 text-blue-700'
          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
      }`}
    >
      {children}
    </Link>
  )
}

function Layout({ children, activeProfileId, onProfileChange }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
          <div className="flex items-center gap-1">
            <Link to="/" className="text-base font-bold text-gray-900 mr-4">
              JobHunter
            </Link>
            <NavLink to="/paste">Paste JD</NavLink>
            <NavLink to="/profile">Profile</NavLink>
            <NavLink to="/tracker">Tracker</NavLink>
          </div>
          <ProfileSwitcher
            activeProfileId={activeProfileId}
            onProfileChange={onProfileChange}
          />
        </div>
      </header>
      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-6">{children}</main>
    </div>
  )
}

function AppRoutes() {
  const [activeProfileId, setActiveProfileId] = useState(null)

  useEffect(() => {
    getSettings()
      .then((r) => {
        const id = r.data.active_profile_id
        if (id) setActiveProfileId(id)
      })
      .catch(() => {})
  }, [])

  return (
    <Layout activeProfileId={activeProfileId} onProfileChange={setActiveProfileId}>
      <Routes>
        <Route path="/" element={<Paste activeProfileId={activeProfileId} />} />
        <Route path="/paste" element={<Paste activeProfileId={activeProfileId} />} />
        <Route path="/profile" element={<Profile activeProfileId={activeProfileId} onProfileChange={setActiveProfileId} />} />
        <Route path="/review/:generationId" element={<Review activeProfileId={activeProfileId} />} />
        <Route path="/tracker" element={<Tracker activeProfileId={activeProfileId} />} />
      </Routes>
    </Layout>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
