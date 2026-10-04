import { useEffect, useRef, useState } from 'react'
import LoadingBar from './LoadingBar'
export default function VideoPreview({ artifactId, authorized, seek, onReady }: { artifactId: string; authorized: boolean; seek?: { seconds: number }; onReady?: (ready: boolean) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [waiting, setWaiting] = useState(true)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(() => { if (seek && video.current) video.current.currentTime = seek.seconds }, [seek])
  function unlock() {
    const panel = document.getElementById('storage-settings') as HTMLDetailsElement | null
    if (panel) { panel.open = true; panel.scrollIntoView({ behavior: 'smooth', block: 'start' }); panel.querySelector<HTMLInputElement>('input')?.focus() }
  }
  return <section className="video-preview" aria-labelledby="video-title">
    <h3 id="video-title">Dein fertiges Video</h3>
    {!authorized ? <button type="button" className="primary-button" onClick={unlock}>Video entsperren</button> : <>
      <video ref={video} key={`${artifactId}-${retry}`} controls playsInline preload="metadata" src={`/api/artifacts/${encodeURIComponent(artifactId)}/content`}
        onLoadStart={() => { setWaiting(true); setError(false); onReady?.(false) }} onWaiting={() => setWaiting(true)} onCanPlay={() => { setWaiting(false); onReady?.(true) }} onLoadedData={() => { setWaiting(false); onReady?.(true) }} onPlaying={() => setWaiting(false)} onError={() => { setWaiting(false); setError(true); onReady?.(false) }} />
      {waiting && !error && <LoadingBar label="Video wird geladen …" />}
      {error && <><p className="notice-error" role="alert">Das Video konnte nicht geladen werden. Bitte Zugang und Medien-Worker prüfen.</p><button type="button" className="secondary-button" onClick={() => setRetry(r => r + 1)}>Video erneut laden</button><button type="button" className="text-button" onClick={unlock}>Videozugriff öffnen</button></>}
      <a className="secondary-button video-download" href={`/api/artifacts/${encodeURIComponent(artifactId)}/content`} download={`video-${artifactId}.mp4`}>MP4 herunterladen</a>
    </>}
  </section>
}
