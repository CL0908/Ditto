// Supabase client (frontend, anon key only — safe to ship).
// 配置来自 .env.local: VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY
import { createClient } from '@supabase/supabase-js'

const url = import.meta.env?.VITE_SUPABASE_URL
const anon = import.meta.env?.VITE_SUPABASE_ANON_KEY

export const supabase =
  url && anon
    ? createClient(url, anon, { realtime: { params: { eventsPerSecond: 20 } } })
    : null

export const hasSupabase = !!supabase
