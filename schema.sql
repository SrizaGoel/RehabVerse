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

