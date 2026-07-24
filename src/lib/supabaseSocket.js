/**
 * Supabase-backed security feed.
 *
 * - 实时事件:订阅 public.security_events 的 INSERT,把每行的 payload(与 mock 完全同构的
 *   JSON:{device,status,risk_score,reason} / {type:'guardian'|'network'|'alert',...})转发给前端。
 *   Python 哨兵(supabase_ingest.py)检测到异常时 insert 一行,仪表盘就实时更新。
 * - HUD 命令按钮(模拟攻击/隔离/复位)仍走本地脚本(startMockBackend),保证现场演示稳定,
 *   不依赖后端在线。两者叠加:真事件从 Supabase 来,按钮从本地来。
 */
import { supabase } from './supabaseClient.js'
import { startMockBackend } from './mockSocket.js'

export function connectSupabaseFeed({ onMessage }) {
  // 本地脚本:BOOT 基线 + 心跳 + 三个命令按钮(演示可靠)
  const local = startMockBackend(onMessage)

  let channel = null
  if (supabase) {
    channel = supabase
      .channel('ditto-security-events')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'security_events' },
        (evt) => {
          const row = evt?.new
          if (!row) return
          // 优先 payload(整条消息);否则用结构化列拼一条设备消息
          const msg = row.payload ?? {
            device: row.device,
            status: row.status,
            risk_score: row.risk_score,
            reason: row.reason ?? [],
          }
          onMessage(msg)
        },
      )
      .subscribe()
  }

  return {
    mode: supabase ? 'supabase' : 'mock',
    simulateAttack: () => local.simulateAttack(),
    quarantine: () => local.quarantine(),
    reset: () => local.reset(),
    close: () => {
      local.close()
      if (channel && supabase) supabase.removeChannel(channel)
    },
  }
}
