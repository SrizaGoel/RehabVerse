create table profiles (
    id uuid primary key
        references auth.users(id)
        on delete cascade,

    full_name text,
    age integer,
    gender text,

    created_at timestamptz default now()
);

create table activities (
    id text primary key,
    title text not null,
    category text not null check (
        category in ('game','challenge')
    ),
    exercise text,
    body_part text,
    movement text
);
create table user_progress (
    user_id uuid primary key
        references profiles(id)
        on delete cascade,
    current_week integer default 1,
    current_day integer default 1,
    morning_completed boolean default false,
    evening_completed boolean default false,
    current_streak integer default 0,
    xp integer default 0,
    updated_at timestamptz default now()
);
create table sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null
        references profiles(id)
        on delete cascade,
    activity_id text not null
        references activities(id),
    completed boolean default false,
    metrics jsonb default '{}'::jsonb,
    created_at timestamptz default now()
);

create table activity_progress (
    user_id uuid not null
        references profiles(id)
        on delete cascade,
    activity_id text not null
        references activities(id),
    progress jsonb default '{}'::jsonb,
    updated_at timestamptz default now(),
    primary key(user_id, activity_id)
);

insert into activities
(id, title, category, exercise, body_part, movement)
values
('forgotten_orchestra', 'Forgotten Orchestra', 'game', 'Side Arm Raise', 'Shoulder', 'Abduction'),
('fishing', 'Fishing Adventure', 'game', 'Elbow Raise', 'Elbow', 'Flexion'),
('paint_the_object', 'Paint the Object', 'challenge', 'Arm Raise', 'Shoulder', 'Abduction'),
('belle_pose', 'Belle Pose', 'challenge', 'Shoulder Rotation', 'Shoulder', 'External Rotation');

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
as $$
begin

  insert into public.profiles (id)
  values (new.id);

  insert into public.user_progress (user_id)
  values (new.id);

  return new;

end;
$$;
create table user_recoveries (

    id uuid primary key default gen_random_uuid(),

    user_id uuid not null
        references profiles(id)
        on delete cascade,

    surgery text not null,

    side text not null,

    current_week integer default 1,

    morning_progress integer default 0,

    morning_total integer default 3,

    morning_completed boolean default false,

    morning_completed_at timestamptz,

    evening_progress integer default 0,

    evening_total integer default 3,

    evening_completed boolean default false,

    created_at timestamptz default now()

);

alter table user_recoveries
  add column morning_completed_ids jsonb not null default '[]'::jsonb,
  add column evening_completed_ids jsonb not null default '[]'::jsonb;