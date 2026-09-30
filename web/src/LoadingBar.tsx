import { useEffect, useState } from 'react'

export default function LoadingBar({ label, startedAt }: { label: string; startedAt?: string }) {
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    if (!startedAt) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [startedAt])
  const start = startedAt ? Date.parse(startedAt) : NaN
  const seconds = Math.max(0, Math.floor((now - start) / 1000))
  return <div className="loading-state">
    <div className="loading-heading">
      <p role="status">{label}</p>
      {Number.isFinite(seconds) && <span className="loading-time" aria-hidden="true">{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}</span>}
    </div>
    <div className="loading-track" role="progressbar" aria-label={label}><span /></div>
  </div>
}
