import { useEffect } from 'react'
import { useSecurityStore, DEVICE_INFO, deviceHealth } from '../state/store.js'

const STATUS_LABEL = {
  normal: { text: '安全', cls: 'ok' },
  warning: { text: '可疑', cls: 'warn' },
  quarantined: { text: '已隔离', cls: 'warn' },
}

/**
 * DeviceInspector — Right-side slide-in panel
 * Only visible when a device is selected; closes with Escape key
 */
export default function DeviceInspector() {
  const selected = useSecurityStore((s) => s.selected)
  const device = useSecurityStore((s) => (selected && s.devices[selected] ? s.devices[selected] : null))
  const select = useSecurityStore((s) => s.select)

  const isOpen = !!device
  const info = device && DEVICE_INFO[selected] ? DEVICE_INFO[selected] : null
  const status = device ? STATUS_LABEL[device.status] || STATUS_LABEL.normal : null
  const score = device ? Math.round(device.risk * 100) : 0
  const warning = device && device.status !== 'normal'

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        select(null)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, select])

  return (
    <aside className={`inspector ${isOpen ? 'open' : ''}`}>
      {device && info && (
        <>
          <div className="insp-head">
            <div>
              <div className="insp-kicker">设备信息</div>
              <div className="insp-name">{info.name}</div>
              <div className="insp-meta">
                {selected} · {info.ip} · {info.protocol}
              </div>
            </div>
            <button className="insp-close" onClick={() => select(null)} aria-label="关闭面板">
              ✕
            </button>
          </div>

          <div className="insp-section">
            <div className="insp-label">状态</div>
            <div className={`status-pill ${device.status === 'normal' ? 'secure' : 'threat'}`}>
              <span className="dot" />
              {status.text}
            </div>
          </div>

          <div className="insp-section">
            <div className="insp-label">
              {selected === 'camera_01' ? '异常评分' : '通信健康度'}
            </div>
            {selected === 'camera_01' ? (
              <div className={`score-big ${status.cls}`}>{score}%</div>
            ) : (
              <div className={`score-big ${deviceHealth(device) > 75 ? 'ok' : 'warn'}`}>
                {deviceHealth(device)}%
              </div>
            )}
          </div>

          <div className="insp-section">
            <div className="insp-label">{warning ? '异常原因' : '分析结果'}</div>
            <ul className="reason-list">
              {warning ? (
                device.reasons.map((r) => <li key={r}>{r}</li>)
              ) : (
                <li className="ok">无 — 行为处于学习基线范围内</li>
              )}
            </ul>
          </div>

          {selected === 'camera_01' && (
            <div className="insp-section">
              <div className="insp-label">基线 vs 当前</div>
              <div className="kv">
                <span className="k">可信端点</span>
                <span className="v">2</span>
                <span className="k">当前通信目标</span>
                <span className="v" style={{ color: warning ? '#d94055' : undefined }}>
                  {warning ? '7 个外部地址' : '2'}
                </span>
              </div>
            </div>
          )}

          <div className="privacy-note">
            TITO 仅分析网络元数据——通信目标、时间与流量大小，
            绝不检查任何视频、音频或消息内容。
          </div>
        </>
      )}
    </aside>
  )
}