# Registration feature

Manual member verification: someone joins the server, fills a form in a private
thread, and a human verifier decides before any role is granted.

Not a continuation of [onboarding](onboarding.md) — that one photographs members and
roles once when the bot joins. The only overlap is the `members` table: approving
someone also enrols them there, because the snapshot has long since run and would
otherwise never see them.

## Flow

```
#registration-locket (public, permanent message)
  └─ [Onboard Me]
       └─ private thread per person (invitable=False, auto_archive=60m)
            └─ [Mahasiswa] / [Alumni]
                 └─ modal form
                      └─ submit → state=pending, auto_archive raised to 7 days
                           └─ review card → #registration-report
                                └─ [Approve] [Reject] [Join Thread]
```

**Approve** → `state=approved` **+ a row in `members`, in one statement** → type role +
prodi role → nickname → result message in the thread → the card is edited in place,
buttons disabled.

**Reject** → reason modal → the reason is posted in the thread → `state=rejected`.
The person may register again from scratch.

`!registration post` (requires *Manage Server*) puts the permanent *Onboard Me*
message in the locket channel. Run it again and it **edits** that message instead of
posting a second one.

Every reply to a registrant is **ephemeral** — `#registration-locket` is public and
its permanent message should not get buried.

## State

One `registrations` row per **attempt**, not per person.

| State                     | Meaning                                              | Clicking Onboard Me again →                            |
| ------------------------- | ---------------------------------------------------- | ------------------------------------------------------ |
| *(no active row)*         | never registered, or every attempt was rejected      | new thread                                             |
| `open`                    | thread alive, form not submitted                     | reuse the thread, `add_user` again, ephemeral with link |
| `pending`                 | submitted, waiting for a verifier                    | ephemeral: "wait for review"                           |
| `approved`                | passed                                               | ephemeral: "already verified"                          |
| `rejected`                | rejected                                             | treated as a new person                                |

The source of truth is the database, not a scan of Discord threads. Archived threads
are not listed by the API, so API-based idempotency leaks in exactly the most common
case.

## Form

A modal takes at most 5 components, and both variants use all five.
`discord.py` 2.7.1 supports a `Select` inside a modal via `ui.Label`, so prodi needs
no separate picking step.

| Mahasiswa                            | Alumni                         |
| ------------------------------------ | ------------------------------ |
| Nama `max_length=32`                 | Nama `max_length=32`           |
| Nama Panggilan `max_length=24`       | Nama Panggilan `max_length=24` |
| NIM `min=max=8`                      | NIM `required=False`           |
| Angkatan `min=max=4`                 | Angkatan `min=max=4`           |
| Prodi `Select` (options = env keys)  | LinkedIn                       |

Validation is pushed onto Discord's built-in constraints: a modal cannot respond with
another modal, so rejecting after submit always costs the person their typing.

Two checks are left in code:

- `angkatan` must be a year between 2000 and the current year. A failure replies
  ephemerally with an **Isi Ulang** button that reopens the modal pre-filled with what
  they already typed.
- NIM is `strip().upper()`-ed — without it `a1b2 ` and `A1B2` are two different NIMs
  and the unique index leaks.

LinkedIn format is deliberately **not** validated. URL regexes are always wrong on the
side that causes trouble, and the verifier opens the link anyway.

Prodi must be a **closed choice** whose values are exactly the env mapping keys. With
free text, "D3 TI" passes verification but gets no prodi role — a silent failure.

## Nickname

Format `[<PRODI>]<nama_panggilan>` — `[D3-TI]Rizky` for mahasiswa, `[ALUMNI]Rizky` for
alumni. The prodi part is the env mapping key upper-cased, so there is no second
display-name table to keep in sync.

Discord's nickname limit is 32 characters: `[ALUMNI]` (8) + `max_length=24` fits
exactly. A long prodi key can still push past 32, in which case the nickname is
truncated — shorten the key if you see it.

A failed nickname change never cancels the approval — the roles are the outcome that
matters, and a server owner's nickname cannot be changed by a bot regardless of
permissions.

## Authorization

**A Discord button can be clicked by anyone who can see the message.** There is no
per-button permission, and `@commands.has_guild_permissions(...)` does not apply to
`ui.Button` callbacks.

```python
def is_verifier(user, verifier_role_id) -> bool:
    return user.guild_permissions.manage_guild or any(
        r.id == verifier_role_id for r in user.roles
    )
```

Checked in **every** callback (Approve, Reject, Join Thread); a failure gets an
ephemeral. Restricting who can see `#registration-report` is a second layer, not the
guard — channel permissions drift quietly, code does not.

`reviewed_by` / `reviewed_at` are always recorded. Identity verification is a decision
that eventually gets questioned; "who let this person in" needs an answer.

## Persistent views

All buttons use `timeout=None` and static `custom_id`s, registered once in
`setup(bot)`. Without this, a bot restart makes every old button reply *"This
interaction failed"* — the message still looks normal, so you only find out after
someone complains.

```python
bot.add_view(OnboardMeView(service, config))   # registration:start
bot.add_view(PilihTipeView(service, config))   # registration:mahasiswa | registration:alumni
bot.add_view(ReviewView(service, config))      # registration:approve | reject | join
```

`add_view` registers a handler for a `custom_id`, not for one message — one
registration revives every old thread and every undecided review card.

**No state inside `custom_id`.** It is sent by the client; putting a `user_id` there
means trusting a number from outside. The code uses `interaction.user.id` (from
Discord, unforgeable) and `interaction.message.id` → `report_message_id` lookup.

## TTL & cleanup

The 15-minute TTL is a **cleanup hint, not a gate**. Discord's
`auto_archive_duration` only accepts 60/1440/4320/10080 minutes, so 15 minutes cannot
be delegated to Discord and has to be our own logic.

- Button clicked while the `open` row is past `expires_at` → delete the old thread,
  create a new one, reset `expires_at`.
- Submitting at minute 20 with the thread still alive → **still accepted**. Rejecting
  it only costs someone who already typed their NIM, and buys nothing.

An hourly sweep (which also runs once at startup) deletes archived threads whose
registration is already decided:

```python
@tasks.loop(hours=1)
async def sweep_archived(self) -> None:
    async for thread in locket.archived_threads(private=True, limit=50):
        reg = await self.service.by_thread(thread.id)
        if reg is None or reg["state"] == "pending":
            continue        # not ours, or the result still needs somewhere to land
        await thread.delete()
        await self.service.clear_thread(thread.id)
```

- **`pending` is never touched** — human verifiers are slow, and the result needs a
  place to be delivered.
- `limit=50` per pass: deleting a thread is a channel-delete operation with an
  aggressive rate limit. The rest get the next hour, nothing is urgent.
- The `reg is None` check matters — do not delete every archived private thread in
  that channel.
- `archived_threads(private=True)` requires the **bot** to have `Manage Threads`.
- Every pass logs one `INFO` line with `scanned` and `swept`, even when it deletes
  nothing — a non-network exception stops the loop permanently, and this line is how
  you notice: `docker logs warden | jq 'select(.swept != null)' | tail -1`.

Not `on_thread_update`: auto-archive is not guaranteed to emit a gateway event, and a
thread archived while the bot was down never gets a catch-up event. The periodic sweep
covers both with one piece of code.

Approve/reject arriving after the thread archived un-archives it first
(`views/threads.py:speak`), then posts.

## Review card

```
┌─ Registrasi Mahasiswa · Percobaan ke-1
│ @rizky_  ·  123456789
│
│ Nama            Muhammad Rizky Ramadhan
│ Nama Panggilan  Rizky
│ Angkatan        2021
│ NIM             A1B2C3D4
│ Prodi           d3-ti
│
│ Akun dibuat     12 Mar 2021    Gabung server  20 Agu 2026
└─ [ Approve ]  [ Reject ]  [ Join Thread ]
```

What has to stand out:

- **⚠️ NIM sudah dipakai @someone** — so it is caught before clicking, not after the
  database rejects it.
- **Percobaan ke-N** — the "rejected 4× with a different NIM each time" pattern is only
  visible if the number is printed.
- **Discord account age** (`member.created_at`) — the only alt-account signal
  available. The date is shown; no automatic rule is built on it.
- **`@user` mention** so the profile can be opened, plus the raw `user_id`, because a
  mention is useless once the person has left the server.

Once decided the card is **edited in place**, not deleted: the color changes, the
footer becomes `Disetujui oleh @verifier`, and all three buttons are disabled.
`#registration-report` becomes a scrollable decision log.

Two verifiers clicking at the same time → the decide `UPDATE` carries
`AND state = 'pending'`, so the loser updates zero rows and gets an ephemeral
*"already decided by @x"*. Approve is an `UPDATE`, so `registrations_active` never
gets a say here — that guard is the only one.

## Join Thread

The bot adds the verifier, rather than the verifier holding `Manage Threads`:

```python
reg = await self.service.by_report_message(interaction.message.id)
thread = await get_thread(interaction.guild, reg["thread_id"])
await thread.add_user(interaction.user)
await interaction.response.send_message(thread.jump_url, ephemeral=True)
```

`Manage Threads` is far larger than the need — it grants deleting, locking and
archiving any thread server-wide, plus visibility into every private thread including
moderation ones. `add_user` grants access to exactly one thread, and the scope is
decided by code rather than by a setting that can drift.

## Rejoining after approval

If an approved person leaves and comes back, `on_member_join` re-grants their roles
and nickname from the stored registration. This is also what covers the case where the
verifier approves someone who has already left.
