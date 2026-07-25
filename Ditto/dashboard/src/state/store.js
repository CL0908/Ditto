import { create } from 'zustand'

const now = () => new Date().toLocaleTimeString('zh-CN')

export const DEVICE_INFO = {
  camera_01: { name: '客厅摄像头', kind: '智能安防摄像头', ip: '192.168.1.64', protocol: 'Wi-Fi · RTSP' },
  light_01: { name: 'Zigbee 智能灯', kind: '吊灯', ip: 'zigbee://0x4A2F', protocol: 'Zigbee 3.0' },
  plug_01: { name: '电源插座', kind: '智能插座', ip: '192.168.1.71', protocol: 'Wi-Fi · MQTT' },
}

const initialDevices = {
  camera_01: { id: 'camera_01', status: 'normal', risk: 0.03, reasons: [] },
  light_01: { id: 'light_01', status: 'normal', risk: 0.01, reasons: [] },
  plug_01: { id: 'plug_01', status: 'normal', risk: 0.02, reasons: [] },
}

export const useSecurityStore = create((set, get) => ({
  devices: initialDevices,
  network: { mode: 'secure', spike: 0 },
  guardian: { state: 'idle', message: '', messageId: 0 },
  alert: null,
  feed: [],
  selected: null,

  select: (id) => set({ selected: id }),

  /**
   * Single entry point for backend data. Accepts JSON messages:
   *   { device:'camera_01', status:'warning', risk_score:0.91, reason:['Unknown IP'] }
   *   { type:'network', mode:'attack', spike:420 }
   *   { type:'guardian', state:'alert', message:'Warning. ...' }
   *   { type:'alert', alert:{ device, detections:[], confidence } }
   */
  applyMessage: (msg) => {
    const s = get()
    const raw = JSON.stringify(msg)
    const isWarn = msg.status === 'warning' || msg.type === 'alert' || msg.mode === 'attack'
    const feed = [...s.feed, { time: now(), raw, warn: !!isWarn }].slice(-6)

    if (msg.type === 'network') {
      set({ network: { mode: msg.mode, spike: msg.spike ?? 0 }, feed })
      return
    }
    if (msg.type === 'guardian') {
      set({
        guardian: { state: msg.state, message: msg.message ?? '', messageId: s.guardian.messageId + 1 },
        feed,
      })
      return
    }
    if (msg.type === 'alert') {
      set({ alert: msg.alert ? { ...msg.alert, time: now() } : null, feed })
      return
    }
    // device payload (spec shape)
    const id = msg.device
    const prev = s.devices[id]
    if (!prev) return
    set({
      devices: {
        ...s.devices,
        [id]: {
          ...prev,
          status: msg.status ?? prev.status,
          risk: msg.risk_score ?? prev.risk,
          reasons: msg.reason ?? prev.reasons,
        },
      },
      feed,
    })
  },
}))

/* -------- derived selectors -------- */

export const selectThreatLevel = (s) => {
  if (s.guardian.state === 'alert') return 'threat'
  if (s.network.mode === 'attack' || s.devices.camera_01.status === 'warning') return 'anomaly'
  return 'secure'
}

export const selectOverallScore = (s) => {
  const cam = s.devices.camera_01
  if (cam.status === 'quarantined') return 88
  if (s.guardian.state === 'alert') return 61
  if (s.network.mode === 'attack') return 72
  if (cam.status === 'warning') return 96 - Math.round(cam.risk * 24)
  return 96
}

export const deviceHealth = (device) => {
  if (device.status === 'quarantined') return 0
  if (device.status === 'warning') return Math.round(device.risk * 100)
  return Math.round((1 - device.risk) * 100)
}
