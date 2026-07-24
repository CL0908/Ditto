import { useEffect, useState } from 'react'
import { useSecurityStore, selectThreatLevel } from '../state/store.js'
import { triggerAttack, triggerQuarantine, triggerReset } from '../lib/useSecurityFeed.js'

function Clock() {
  const [time, setTime] = useState(() => new Date().toLocaleTimeString('zh-CN'))
  useEffect(() => {
    const id = setInterval(() => setTime(new Date().toLocaleTimeString('zh-CN')), 1000)
    return () => clearInterval(id)
  }, [])
  return <div className="hud-clock">{time}</div>
}

/* Tito's typewriter messages — fixed top-right below the header,
   a DOM overlay so it never overlaps the 3D assets */
function GuardianBubble() {
  const guardian = useSecurityStore((s) => s.guardian)
  const [shown, setShown] = useState('')

  useEffect(() => {
    setShown('')
    if (!guardian.message) return
    let i = 0
    const id = setInterval(() => {
      i += 2
      setShown(guardian.message.slice(0, i))
      if (i >= guardian.message.length) clearInterval(id)
    }, 28)
    return () => clearInterval(id)
  }, [guardian.message, guardian.messageId])

  if (!guardian.message) return null
  const alert = guardian.state === 'alert'
  return (
    <div className={`guardian-bubble ${alert ? 'alert' : ''}`}>
      <div className="who">Tito 守护者 · {alert ? '威胁警报' : guardian.state === 'detecting' ? '分析中' : '在线'}</div>
      {shown}
      {shown.length < guardian.message.length && <span className="cursor" />}
    </div>
  )
}

/* Collapsible security feed pinned to the bottom edge */
function AlertFeed() {
  const feed = useSecurityStore((s) => s.feed)
  const [open, setOpen] = useState(false)

  return (
    <div className="alert-feed" data-open={open}>
      <div className="feed-header" onClick={() => setOpen(!open)}>
        <span>安全动态 · {feed.length} 条事件</span>
        <span className="toggle">▼</span>
      </div>
      <div className="feed-scroll">
        {feed.length === 0 && <div className="feed-line">等待遥测数据…</div>}
        {[...feed].reverse().map((f, i) => (
          <div key={i} className={`feed-line ${f.warn ? 'warn' : ''}`}>
            <span className="t">{f.time}</span>
            {f.raw}
          </div>
        ))}
      </div>
    </div>
  )
}

/* Demo controls docked at the right of the footer */
function Controls() {
  const level = useSecurityStore(selectThreatLevel)
  const camStatus = useSecurityStore((s) => s.devices.camera_01.status)
  const idle = level === 'secure'

  return (
    <div className="hud-controls">
      <button className="btn btn-attack" disabled={!idle} onClick={triggerAttack}>
        ▲ 模拟攻击
      </button>
      {!idle && camStatus !== 'quarantined' && (
        <button className="btn btn-safe" onClick={triggerQuarantine}>
          隔离设备
        </button>
      )}
      {!idle && (
        <button className="btn" onClick={triggerReset}>
          重置演示
        </button>
      )}
    </div>
  )
}

function Legend() {
  return (
    <div className="legend">
      <span><i className="l-blue" />可信流量</span>
      <span><i className="l-red" />异常流量</span>
      <span><i className="l-green" />设备健康</span>
      <span className="hint">拖动旋转视角 · 点击设备或 Tito</span>
      <Controls />
    </div>
  )
}

/* Returns the 3D camera to the whole-apartment overview */
function OverviewButton() {
  const selected = useSecurityStore((s) => s.selected)
  const select = useSecurityStore((s) => s.select)
  return (
    <button className="btn view-btn" disabled={!selected} onClick={() => select(null)} title="返回全屋视角">
      ⌂ 总览
    </button>
  )
}

/** Sparse command chrome: fixed header + fixed footer (feed, legend, controls) */
export default function SecurityDashboard() {
  const level = useSecurityStore(selectThreatLevel)
  const pillText = level === 'secure' ? '安全' : level === 'anomaly' ? '检测到异常' : '威胁活跃'

  return (
    <>
      <header className="hud-top">
        <div className="brand">
          <a className="btn view-btn back-home" href="../index.html" title="返回 Ditto 网站首页">← 返回首页</a>
          <div className="brand-mark"><img src="tito-icon.png" alt="TITO logo" /></div>
          <div>
            <div className="brand-title">TITO <span>· 家庭免疫系统</span></div>
            <div className="brand-sub">行为式 AI 安全 · 仅元数据监控</div>
          </div>
        </div>
        <div className={`status-pill ${level}`}>
          <span className="dot" />
          {pillText}
        </div>
        <div className="hud-right">
          <OverviewButton />
          <div className="live-feed"><span className="dot" />实时画面</div>
          <Clock />
        </div>
      </header>

      <GuardianBubble />

      <div className="bottom-dock">
        <Legend />
        <AlertFeed />
      </div>
    </>
  )
}
