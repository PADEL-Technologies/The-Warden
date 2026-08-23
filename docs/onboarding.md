# Onboarding feature

Snapshots every member and their roles the first time the bot joins a guild. It is a
point-in-time baseline — it is **not** kept in sync afterwards.

- **Bot joins a new guild** → automatic snapshot, one database transaction.
- **Bot is kicked and re-invited** → the existing snapshot is kept, no re-snapshot.
- **`!onboard existing`** (requires *Manage Server*) → snapshot manually, e.g. if the
  feature was disabled when the bot joined.
- **`!onboard existing --force`** → replace the guild's snapshot. The old rows are
  deleted inside the same transaction as the new ones.

`@everyone` and managed roles (bot/integration roles, including Nitro Booster) are never
stored — they are not human-managed roles. Bot accounts are not stored as members;
`member_count` counts humans only.

The role and channel catalogs come from the guild itself, not from what members hold:
roles and channels with zero members/users are still recorded.

The snapshot is written as one transaction across `roles`, `members`, `member_roles`,
`channels` and `onboardings`, so a partial snapshot is never left behind. `onboardings`
records who triggered it (`NULL` = automatic) and the member count at the time.

The roster is chunked (`guild.chunk()`) before snapshotting: on a runtime join the
member list is not populated yet. This is why the **Server Members** privileged
intent is required.

Toggle with `ONBOARDING_ENABLED` — see [Configuration](configuration.md).
