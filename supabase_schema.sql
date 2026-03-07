-- ============================================================
-- Campus Lost & Found — Supabase Database Schema
-- Run these SQL statements in Supabase SQL Editor
-- ============================================================

-- ── Enable UUID extension ─────────────────────────────────
create extension if not exists "uuid-ossp";

-- ── USERS ─────────────────────────────────────────────────
create table if not exists public.users (
    id          uuid primary key references auth.users(id) on delete cascade,
    email       text unique not null,
    full_name   text not null,
    student_id  text unique not null,
    department  text not null,
    phone       text,
    created_at  timestamptz default now()
);

alter table public.users enable row level security;

create policy "Users can view own profile"
    on public.users for select
    using (auth.uid() = id);

create policy "Users can update own profile"
    on public.users for update
    using (auth.uid() = id);

-- ── LOST ITEMS ────────────────────────────────────────────
create table if not exists public.lost_items (
    id            uuid primary key default uuid_generate_v4(),
    user_id       uuid not null references public.users(id) on delete cascade,
    item_name     text not null,
    description   text not null,
    location      text not null,
    date_lost     date not null,
    category      text not null,
    contact_info  text not null,
    image_url     text,
    status        text not null default 'lost' check (status in ('lost','found','returned','closed')),
    created_at    timestamptz default now(),
    updated_at    timestamptz default now()
);

alter table public.lost_items enable row level security;

-- Anyone can read lost items
create policy "Anyone can view lost items"
    on public.lost_items for select
    using (true);

-- Only authenticated users can insert
create policy "Authenticated users can report lost items"
    on public.lost_items for insert
    with check (auth.uid() = user_id);

-- Only owner can update
create policy "Owners can update their lost items"
    on public.lost_items for update
    using (auth.uid() = user_id);

-- Only owner can delete
create policy "Owners can delete their lost items"
    on public.lost_items for delete
    using (auth.uid() = user_id);

-- Full-text search index
create index if not exists idx_lost_items_search
    on public.lost_items using gin(to_tsvector('english', item_name || ' ' || description));

create index if not exists idx_lost_items_location on public.lost_items (location);
create index if not exists idx_lost_items_category on public.lost_items (category);
create index if not exists idx_lost_items_status   on public.lost_items (status);
create index if not exists idx_lost_items_user     on public.lost_items (user_id);

-- ── FOUND ITEMS ───────────────────────────────────────────
create table if not exists public.found_items (
    id               uuid primary key default uuid_generate_v4(),
    user_id          uuid not null references public.users(id) on delete cascade,
    item_name        text not null,
    description      text not null,
    location         text not null,
    date_found       date not null,
    category         text not null,
    image_url        text,
    storage_location text,
    status           text not null default 'found' check (status in ('lost','found','returned','closed')),
    created_at       timestamptz default now(),
    updated_at       timestamptz default now()
);

alter table public.found_items enable row level security;

create policy "Anyone can view found items"
    on public.found_items for select
    using (true);

create policy "Authenticated users can report found items"
    on public.found_items for insert
    with check (auth.uid() = user_id);

create policy "Owners can update their found items"
    on public.found_items for update
    using (auth.uid() = user_id);

create policy "Owners can delete their found items"
    on public.found_items for delete
    using (auth.uid() = user_id);

create index if not exists idx_found_items_search
    on public.found_items using gin(to_tsvector('english', item_name || ' ' || description));

create index if not exists idx_found_items_location on public.found_items (location);
create index if not exists idx_found_items_category on public.found_items (category);
create index if not exists idx_found_items_status   on public.found_items (status);
create index if not exists idx_found_items_user     on public.found_items (user_id);

-- ── MESSAGES ──────────────────────────────────────────────
create table if not exists public.messages (
    id          uuid primary key default uuid_generate_v4(),
    sender_id   uuid not null references public.users(id) on delete cascade,
    receiver_id uuid not null references public.users(id) on delete cascade,
    item_id     uuid not null,
    item_type   text not null check (item_type in ('lost','found')),
    content     text not null,
    is_read     boolean default false,
    created_at  timestamptz default now()
);

alter table public.messages enable row level security;

create policy "Users can view their own messages"
    on public.messages for select
    using (auth.uid() = sender_id or auth.uid() = receiver_id);

create policy "Authenticated users can send messages"
    on public.messages for insert
    with check (auth.uid() = sender_id);

create policy "Receivers can mark messages read"
    on public.messages for update
    using (auth.uid() = receiver_id);

create index if not exists idx_messages_receiver on public.messages (receiver_id);
create index if not exists idx_messages_sender   on public.messages (sender_id);
create index if not exists idx_messages_item     on public.messages (item_id, item_type);

-- ── STORAGE BUCKET ────────────────────────────────────────
-- Run in Supabase Dashboard → Storage → Create bucket "item-images" (public)
-- Or via SQL:
-- insert into storage.buckets (id, name, public) values ('item-images', 'item-images', true);

-- Storage policies (run after creating the bucket)
create policy "Public read access"
    on storage.objects for select
    using (bucket_id = 'item-images');

create policy "Authenticated upload"
    on storage.objects for insert
    with check (bucket_id = 'item-images' and auth.role() = 'authenticated');

create policy "Owner delete"
    on storage.objects for delete
    using (bucket_id = 'item-images' and auth.uid()::text = (storage.foldername(name))[1]);

-- ── AUTO UPDATE updated_at ────────────────────────────────
create or replace function public.handle_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger on_lost_item_update
    before update on public.lost_items
    for each row execute procedure public.handle_updated_at();

create trigger on_found_item_update
    before update on public.found_items
    for each row execute procedure public.handle_updated_at();
