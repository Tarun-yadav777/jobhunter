import axios from 'axios'

const client = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

// ── Profiles ─────────────────────────────────────────────────────────────────

export const getProfiles = () => client.get('/profiles')
export const getProfile = (id) => client.get(`/profiles/${id}`)
export const getProfileStatus = (id) => client.get(`/profiles/${id}/status`)
export const createProfile = (formData) =>
  client.post('/profiles', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
export const patchProfile = (id, data) => client.patch(`/profiles/${id}`, data)
export const deleteProfile = (id) => client.delete(`/profiles/${id}`)
export const activateProfile = (id) => client.post(`/profiles/${id}/activate`)
export const reembedProfile = (id) => client.post(`/profiles/${id}/reembed`)

export const getPreferences = (id) => client.get(`/profiles/${id}/preferences`)
export const updatePreferences = (id, data) => client.put(`/profiles/${id}/preferences`, data)

// ── Settings ──────────────────────────────────────────────────────────────────

export const getSettings = () => client.get('/settings')
export const patchSettings = (data) => client.patch('/settings', data)

// ── Jobs ─────────────────────────────────────────────────────────────────────

export const pasteJob = (data) => client.post('/jobs/paste', data)
export const getJob = (id) => client.get(`/jobs/${id}`)
export const getJobs = () => client.get('/jobs')

// ── Generate ─────────────────────────────────────────────────────────────────

export const startGeneration = (data) => client.post('/generate', data)
export const getGenerationStatus = (id) => client.get(`/generate/${id}/status`)
export const getGeneration = (id) => client.get(`/generate/${id}`)
export const patchResume = (id, data) => client.patch(`/generate/${id}/resume`, data)
export const patchCoverLetter = (id, data) => client.patch(`/generate/${id}/cover-letter`, data)
export const approveGeneration = (id) => client.post(`/generate/${id}/approve`)

// ── Tracker ──────────────────────────────────────────────────────────────────

export const getTracker = (params) => client.get('/tracker', { params })
export const getTrackerResume = (id) => client.get(`/tracker/${id}/resume`)
export const getTrackerCoverLetter = (id) => client.get(`/tracker/${id}/cover-letter`)
export const downloadResume = (id) =>
  client.get(`/tracker/${id}/resume/download`, { responseType: 'blob' })

export default client
