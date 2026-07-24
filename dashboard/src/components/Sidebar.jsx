import { useSecurityStore, selectOverallScore, selectThreatLevel, deviceHealth, DEVICE_INFO } from '../state/store.js'

/**
 * Sidebar — fixed left rail.
 * System health score, clickable device list, active alert summary, privacy note.
 * Clicking a device selects it (opens the inspector + focuses the 3D camera).
 */
export default function Sidebar() {
  const score = useSecurityStore(selectOverallScore)
  const level = useSecurityStore(selectThreatLevel)
  const devices = useSecurityStore((s) => s.devices)
  const selected = useSecurityStore((s) => s.selected)
  const select = useSecurityStore((s) => s.select)
  const alert = useSecurityStore((s) => s.alert)

  const threatCount = Object.values(devices).filter((d) => d.status === 'warning').length

  return (
    <aside className="sidebar">
      {/* System health */}
      <div className="metric-card">
        <div className="metric-label">系统健康度</div>
        <div className={`metric-value ${score < 80 ? 'warn' : ''}`}>{score}%</div>
        <div className="metric-status">
          {level === 'secure' ? '所有系统正常' : level === 'anomaly' ? '检测到异常' : '威胁活跃'}
        </div>
      </div>

      {/* Active alerts */}
      {(alert || threatCount > 0) && (
        <div className="alert-summary">
          <span className="alert-icon">▲</span>
          <span className="alert-text">
            {alert ? `1 条活跃警报 — ${alert.device}` : `${threatCount} 条活跃警报`}
          </span>
        </div>
      )}

      {/* Device list */}
      <div className="device-list">
        <div className="list-title">设备列表</div>
        {Object.entries(devices).map(([key, device]) => {
          const info = DEVICE_INFO[key]
          const health = deviceHealth(device)
          const warn = device.status !== 'normal'
          return (
            <div
              key={key}
              className={`device-item ${selected === key ? 'selected' : ''}`}
              onClick={() => select(selected === key ? null : key)}
            >
              <span className={`device-dot ${device.status}`} />
              <div className="device-name-column">
                <span className="device-name">{info?.name ?? key}</span>
                <span className="device-meta">{info?.protocol ?? ''}</span>
              </div>
              <span className={`device-health ${warn ? 'warn' : ''}`}>{health}%</span>
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="privacy-note">
          仅分析元数据：通信目标、时间与流量大小——不检查任何内容。
        </div>
      </div>
    </aside>
  )
}
