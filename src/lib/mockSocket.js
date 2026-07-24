/**
 * Security feed connection.
 *
 * If VITE_WS_URL is defined, connects to the real backend over WebSocket and
 * forwards every message (JSON string) to onMessage. Otherwise a mock backend
 * is simulated in-browser, emitting the exact same JSON payloads:
 *
 *   { device:'camera_01', status:'warning', risk_score:0.91, reason:['Unknown IP'] }
 *
 * Commands (simulateAttack / quarantine / reset) are sent to the real socket
 * when connected, or executed against the mock timeline otherwise.
 */

const ATTACK_SCRIPT = [
  { at: 0, msg: { device: 'camera_01', status: 'warning', risk_score: 0.12, reason: ['异常通信时间'] } },
  { at: 900, msg: { device: 'camera_01', status: 'warning', risk_score: 0.34, reason: ['异常通信时间'] } },
  { at: 1800, msg: { device: 'camera_01', status: 'warning', risk_score: 0.58, reason: ['异常通信时间', '流量激增'] } },
  { at: 2500, msg: { type: 'network', mode: 'attack', spike: 420 } },
  { at: 2700, msg: { device: 'light_01', status: 'warning', risk_score: 0.22, reason: ['Zigbee 信道指令洪泛'] } },
  { at: 3300, msg: { type: 'guardian', state: 'detecting', message: '检测到异常，正在与学习基线比对…', speak: false } },
  { at: 4600, msg: { device: 'camera_01', status: 'warning', risk_score: 0.91, reason: ['未知 IP', '流量激增', '异常通信时间'] } },
  {
    at: 4750,
    msg: {
      type: 'alert',
      alert: {
        device: '客厅摄像头',
        detections: ['未知目标 IP', '检测到流量异常', '行为偏离基线'],
        confidence: 0.91,
      },
    },
  },
  {
    at: 4950,
    msg: {
      type: 'guardian',
      state: 'alert',
      message: '警告：客厅摄像头的行为偏离正常基线，检测到未知通信。',
    },
  },
]

const QUARANTINE_SCRIPT = [
  { at: 0, msg: { type: 'guardian', state: 'idle', message: '正在隔离设备，流量已切换至可信网关，威胁已得到控制。' } },
  { at: 250, msg: { type: 'network', mode: 'secure', spike: 0 } },
  { at: 500, msg: { device: 'camera_01', status: 'quarantined', risk_score: 0.91, reason: ['未知 IP', '流量激增'] } },
  { at: 700, msg: { device: 'light_01', status: 'normal', risk_score: 0.01, reason: [] } },
  { at: 900, msg: { type: 'alert', alert: null } },
]

const RESET_SCRIPT = [
  { at: 0, msg: { type: 'alert', alert: null } },
  { at: 150, msg: { type: 'network', mode: 'secure', spike: 0 } },
  { at: 300, msg: { device: 'camera_01', status: 'normal', risk_score: 0.03, reason: [] } },
  { at: 450, msg: { device: 'light_01', status: 'normal', risk_score: 0.01, reason: [] } },
  { at: 600, msg: { device: 'plug_01', status: 'normal', risk_score: 0.02, reason: [] } },
  { at: 800, msg: { type: 'guardian', state: 'idle', message: '基线已恢复，所有设备行为正常。', speak: false } },
]

const BOOT_SCRIPT = [
  { at: 400, msg: { device: 'camera_01', status: 'normal', risk_score: 0.03, reason: [] } },
  { at: 550, msg: { device: 'light_01', status: 'normal', risk_score: 0.01, reason: [] } },
  { at: 700, msg: { device: 'plug_01', status: 'normal', risk_score: 0.02, reason: [] } },
  { at: 900, msg: { type: 'network', mode: 'secure', spike: 0 } },
  { at: 1200, msg: { type: 'guardian', state: 'idle', message: 'Tito 守护者已上线，行为基线加载完成，正在监控 3 台设备。', speak: false } },
]

export function startMockBackend(onMessage) {
  let timers = []
  let attacking = false

  const emit = (obj) => onMessage(JSON.stringify(obj))
  const runScript = (script) => {
    timers.forEach(clearTimeout)
    timers = script.map(({ at, msg }) => setTimeout(() => emit(msg), at))
  }

  const heartbeat = setInterval(() => {
    if (attacking) return
    emit({ device: 'plug_01', status: 'normal', risk_score: +(0.01 + Math.random() * 0.03).toFixed(2) })
  }, 5000)

  runScript(BOOT_SCRIPT)

  return {
    mode: 'mock',
    simulateAttack() {
      attacking = true
      runScript(ATTACK_SCRIPT)
    },
    quarantine() {
      attacking = false
      runScript(QUARANTINE_SCRIPT)
    },
    reset() {
      attacking = false
      runScript(RESET_SCRIPT)
    },
    close() {
      clearInterval(heartbeat)
      timers.forEach(clearTimeout)
    },
  }
}

function connectRealBackend(url, onMessage) {
  let ws
  try {
    ws = new WebSocket(url)
  } catch {
    return null
  }
  let opened = false
  let fallback = null

  const ensureFallback = () => {
    if (!fallback) fallback = startMockBackend(onMessage)
    return fallback
  }

  const fallbackTimer = setTimeout(() => {
    if (!opened) ensureFallback()
  }, 2000)

  ws.onopen = () => { opened = true }
  ws.onmessage = (e) => onMessage(e.data)
  ws.onerror = () => { if (!opened) ensureFallback() }
  ws.onclose = () => { if (!opened) ensureFallback() }

  const send = (obj) => {
    if (opened && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj))
    else ensureFallback()
  }

  return {
    mode: 'websocket',
    simulateAttack() {
      if (opened) send({ command: 'simulate_attack' })
      else ensureFallback().simulateAttack()
    },
    quarantine() {
      if (opened) send({ command: 'quarantine' })
      else ensureFallback().quarantine()
    },
    reset() {
      if (opened) send({ command: 'reset' })
      else ensureFallback().reset()
    },
    close() {
      clearTimeout(fallbackTimer)
      try { ws.close() } catch { /* noop */ }
      fallback?.close()
    },
  }
}

export function connectSecurityFeed({ onMessage }) {
  const url = import.meta.env?.VITE_WS_URL
  if (url) {
    const real = connectRealBackend(url, onMessage)
    if (real) return real
  }
  return startMockBackend(onMessage)
}
