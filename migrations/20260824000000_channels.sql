-- +goose Up
-- Snapshot channel guild saat onboarding, sama seperti roles/members.
-- Tanpa FK, sama seperti 20260822000000_init.sql.
CREATE TABLE channels (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id     BIGINT NOT NULL,
    channel_id   BIGINT NOT NULL,             -- snowflake Discord
    channel_name TEXT NOT NULL,
    channel_type TEXT NOT NULL,               -- text | voice | category | ...
    UNIQUE (guild_id, channel_id)
);

-- +goose Down
DROP TABLE channels;
