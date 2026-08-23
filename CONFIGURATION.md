# Configuration

All settings come from environment variables (or `.env` for `make docker-run`):

| Variable            | Default           | Purpose                              |
| ------------------- | ----------------- | ------------------------------------ |
| `DISCORD_TOKEN`     | — (required)      | Bot token                            |
| `DATABASE_URL`      | — (required)      | Postgres DSN, e.g. `postgres://user:pass@host:5432/db` |
| `ONBOARDING_ENABLED`| `true`            | Load the onboarding feature at all   |
| `REGISTRATION_ENABLED` | `true`         | Load the registration feature at all |

When `REGISTRATION_ENABLED` is true, these are **required** — the feature is dead
without them, so it fails at startup rather than going quiet when the first
person clicks a button:

| Variable                          | Purpose                                     |
| --------------------------------- | ------------------------------------------- |
| `REGISTRATION_LOCKET_CHANNEL_ID`  | Public channel holding the *Onboard Me* message |
| `REGISTRATION_REPORT_CHANNEL_ID`  | Where review cards are posted               |
| `REGISTRATION_VERIFIER_ROLE_ID`   | Role allowed to approve/reject              |
| `REGISTRATION_MAHASISWA_ROLE_ID`  | Granted on approval, type `mahasiswa`       |
| `REGISTRATION_ALUMNI_ROLE_ID`     | Granted on approval, type `alumni`          |
| `REGISTRATION_PRODI_ROLES`        | `d3-ti:333,d3-tk:444` — keys are the prodi options in the form |

The bot needs the **Server Members** privileged intent — enable it in the
Discord Developer Portal, it is already requested in `warden/bot.py`.
