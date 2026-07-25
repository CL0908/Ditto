-- Ditto Supabase schema —— 在 Supabase Dashboard → SQL Editor 粘贴运行一次。
-- 前端(anon)只读订阅;写入由后端(service_role)完成。

create table if not exists public.security_events (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  payload     jsonb not null,              -- 整条消息(与前端 mock 同构)
  device      text,                        -- 冗余列,便于 SQL 查询/看板
  status      text,
  risk_score  real
);

create index if not exists security_events_created_idx
  on public.security_events (created_at desc);

-- RLS:anon 只能读(Realtime 订阅需要 select 权限);写入走 service_role(绕过 RLS)
alter table public.security_events enable row level security;

drop policy if exists "anon read security_events" on public.security_events;
create policy "anon read security_events"
  on public.security_events for select to anon using (true);

-- 打开 Realtime 推送
alter publication supabase_realtime add table public.security_events;
