export default function Paste({ activeProfileId }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Paste Job Description</h1>
        <p className="text-sm text-gray-500 mt-1">Coming in Session 9.</p>
      </div>
      {!activeProfileId && (
        <div className="card p-4 border-yellow-200 bg-yellow-50">
          <p className="text-sm text-yellow-800">
            No active profile selected. Go to <a href="/profile" className="underline font-medium">Profiles</a> to create or activate one.
          </p>
        </div>
      )}
    </div>
  )
}
