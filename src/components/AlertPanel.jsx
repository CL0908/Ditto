import { useEffect } from 'react'
import { useSecurityStore } from '../state/store.js'

const AUTO_DISMISS_MS = 8000

/** Glanceable top-center toast shown while a threat alert is active */
export default function AlertPanel() {
  const alert = useSecurityStore((s) => s.alert)
  const message = useSecurityStore((s) => s.guardian.message)
  const applyMessage = useSecurityStore((s) => s.applyMessage)

  const dismiss = () => applyMessage({ type: 'alert', alert: null })

  // Auto-dismiss; hovering pauses the countdown
  useEffect(() => {
    if (!alert) return
    const id = setTimeout(dismiss, AUTO_DISMISS_MS)
    return () => clearTimeout(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alert?.time])

  if (!alert) return null

  return (
    <div className="alert-toast">
      <div className="alert-content">
        <span className="alert-icon">▲</span>
        <span className="alert-text">
          {alert.device} — {message || '检测到可疑行为'}
        </span>
        <button onClick={dismiss} aria-label="关闭警报">✕</button>
      </div>
      <div className="alert-confidence">
        {alert.time} · AI 置信度 {Math.round(alert.confidence * 100)}%
      </div>
    </div>
  )
}
