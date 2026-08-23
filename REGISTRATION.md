# Registration feature

Manual member verification. Design notes: [`docs/registration-design.md`](docs/registration-design.md).

```
#registration-locket  [Onboard Me]  →  private thread  →  [Mahasiswa]/[Alumni]
  →  modal form  →  review card in #registration-report  →  [Approve]/[Reject]/[Join Thread]
```

- `!registration post` (requires *Manage Server*) puts the permanent *Onboard Me*
  message in the locket channel. Run it again and it **edits** that message
  instead of posting a second one.
- Approve grants the type role plus the prodi role and sets the nickname to
  `[D3-TI]Rizky` / `[ALUMNI]Rizky`. A failed nickname change never cancels the
  approval.
- Reject asks for a reason, posts it in the thread, and lets the person register
  again from scratch.
- One row per **attempt** in `registrations`; the database, not the code, enforces
  one live registration per person and one approved registration per NIM.
- An hourly sweep deletes archived threads whose registration is already decided.
  `pending` threads are never touched.

Server setup this feature assumes:

| Who                     | Permission                                       |
| ----------------------- | ------------------------------------------------ |
| Bot                     | `Manage Threads`, `Manage Roles`, `Manage Nicknames` |
| Bot                     | its role must sit **above** every role it grants  |
| `@everyone`             | **revoke** `Change Nickname`                      |
| Verifier role           | **no** `Manage Threads` — the bot does `add_user` |
| `#registration-report`  | restrict who can see it (second layer, not the guard) |

Two failures that look like success if the setup is wrong: the bot's role sitting
below a target role (`add_roles` raises `Forbidden`), and the person leaving the
server before a verifier decides (roles land on their next join instead). Both are
caught and reported to the verifier.
