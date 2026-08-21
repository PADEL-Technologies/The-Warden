-- Baseline schema. Tanpa FK eksplisit — relasi didokumentasikan, dijaga oleh repo.
-- roles.id   <- member_roles.role_id
-- members.id <- member_roles.member_id
CREATE TABLE IF NOT EXISTS roles (
    id        INTEGER PRIMARY KEY,
    guild_id  INTEGER NOT NULL,
    role_id   INTEGER NOT NULL UNIQUE,   -- snowflake Discord
    role_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS members (
    id        INTEGER PRIMARY KEY,
    guild_id  INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,          -- snowflake Discord
    joined_at TEXT,
    UNIQUE (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS member_roles (
    member_id INTEGER NOT NULL,          -- members.id
    role_id   INTEGER NOT NULL,          -- roles.id
    PRIMARY KEY (member_id, role_id)
);

CREATE TABLE IF NOT EXISTS onboardings (
    guild_id     INTEGER PRIMARY KEY,
    onboarded_at TEXT NOT NULL,
    triggered_by INTEGER,                -- NULL = auto saat bot join
    member_count INTEGER NOT NULL
);
