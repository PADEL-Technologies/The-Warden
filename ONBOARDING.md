# Onboarding feature

Snapshots every member and their roles the first time the bot joins a guild
(point-in-time baseline — it is not kept in sync afterwards):

- **Bot joins a new guild** → auto-snapshot, one database transaction.
- **Bot is kicked and re-invited** → existing snapshot is kept, no re-snapshot.
- **`!onboard existing`** (requires *Manage Server*) → snapshot manually, e.g.
  if the feature was disabled when the bot joined.
- **`!onboard existing --force`** → replace the guild's snapshot.

`@everyone` is never stored (everyone has it, it carries no information).
