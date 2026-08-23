-- +goose Up
-- Baseline schema. Tanpa FK eksplisit — relasi didokumentasikan, dijaga oleh repo.
-- roles.id   <- member_roles.role_id
-- members.id <- member_roles.member_id
CREATE TABLE roles (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id  BIGINT NOT NULL,
    role_id   BIGINT NOT NULL,             -- snowflake Discord
    role_name TEXT NOT NULL,
    UNIQUE (guild_id, role_id)
);

CREATE TABLE members (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id  BIGINT NOT NULL,
    user_id   BIGINT NOT NULL,             -- snowflake Discord
    joined_at TEXT,
    UNIQUE (guild_id, user_id)
);

CREATE TABLE member_roles (
    member_id BIGINT NOT NULL,             -- members.id
    role_id   BIGINT NOT NULL,             -- roles.id
    PRIMARY KEY (member_id, role_id)
);

CREATE TABLE onboardings (
    guild_id     BIGINT PRIMARY KEY,
    onboarded_at timestamptz NOT NULL DEFAULT now(),
    triggered_by BIGINT,                   -- NULL = auto saat bot join
    member_count INTEGER NOT NULL
);

-- +goose Down
DROP TABLE onboardings;
DROP TABLE member_roles;
DROP TABLE members;
DROP TABLE roles;
