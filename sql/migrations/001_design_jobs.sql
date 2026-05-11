-- Run this once against Vercel Postgres (Neon) or any Postgres instance.

create extension if not exists pgcrypto;

create table if not exists design_jobs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  user_prompt text not null,
  session_id text,
  status text not null default 'queued'
    check (status in ('queued','processing','done','failed','rejected')),
  pre_filter jsonb,
  attempts jsonb default '[]'::jsonb,
  final_image_url text,
  reason_code text,
  total_latency_ms int,
  image_bytes bytea,
  image_mime text default 'image/png'
);

create index if not exists design_jobs_status_idx on design_jobs(status);
create index if not exists design_jobs_created_at_idx on design_jobs(created_at desc);

create or replace function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists design_jobs_updated_at on design_jobs;
create trigger design_jobs_updated_at
  before update on design_jobs
  for each row execute function set_updated_at();
