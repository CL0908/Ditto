import { useEffect } from 'react'
import { useSecurityStore } from '../state/store.js'
import { connectSecurityFeed } from './mockSocket.js'
import { connectSupabaseFeed } from './supabaseSocket.js'
import { hasSupabase } from './supabaseClient.js'
import { speak } from './speech.js'

// 配了 Supabase 就走实时后端,否则用 mock/WS
const connectFeed = hasSupabase ? connectSupabaseFeed : connectSecurityFeed

let activeConnection = null

/** Wire the (mock or real) WebSocket feed into the global store. */
export function useSecurityFeed() {
  const applyMessage = useSecurityStore((s) => s.applyMessage)

  useEffect(() => {
    const onMessage = (raw) => {
      let msg
      try {
        msg = typeof raw === 'string' ? JSON.parse(raw) : raw
      } catch {
        return
      }
      applyMessage(msg)
      if (msg.type === 'guardian' && msg.message && msg.speak !== false) {
        speak(msg.message)
      }
    }

    const conn = connectFeed({ onMessage })
    activeConnection = conn
    return () => {
      conn.close()
      if (activeConnection === conn) activeConnection = null
    }
  }, [applyMessage])
}

/* -------- commands used by the HUD -------- */

export function triggerAttack() {
  activeConnection?.simulateAttack()
}

export function triggerQuarantine() {
  activeConnection?.quarantine()
}

export function triggerReset() {
  activeConnection?.reset()
}

/** Guardian explains itself when the user clicks the orb. */
export function guardianIntroduce() {
  const { applyMessage } = useSecurityStore.getState()
  const state = useSecurityStore.getState().guardian.state
  applyMessage({
    type: 'guardian',
    state,
    message: '我只分析设备的行为模式，从不查看您的任何内容——您的隐私始终受到保护。',
  })
}
