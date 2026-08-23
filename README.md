# warden

Discord bot.

## Run

```bash
uv sync
DISCORD_TOKEN=... DATABASE_URL=postgres://... uv run main.py
```

Or via `make install` / `DISCORD_TOKEN=... DATABASE_URL=postgres://... make run`
(same commands, see `Makefile`).

## Checks

```bash
make check   # ruff check + ruff format --check + pytest
```

Same three commands run in CI on every push and PR.

## Configuration

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

## Database & migrations

PostgreSQL via `asyncpg`. Migrations are managed by
[goose](https://github.com/pressly/goose) — plain SQL files in `migrations/`
with `-- +goose Up` / `-- +goose Down` sections. Migration runs are recorded
in goose's `goose_db_version` table.

Local dev setup:

```bash
make db                # docker compose up -d: postgres:18 on localhost:5432 (warden/warden)
export DATABASE_URL=postgres://warden:warden@localhost:5432/warden
make migrate-up        # apply pending migrations
make migration NAME=add_left_at   # scaffold a new migration (goose create -s)
```

Install the goose binary once
([releases](https://github.com/pressly/goose/releases), or
`make goose-install` which pins `v3.24.3`). The app itself
never runs migrations — apply them as a separate step (or in CI) before
starting the bot.

Tests that need a real database set `WARDEN_TEST_DATABASE_URL` and are
skipped otherwise:

```bash
make db
goose -dir migrations postgres postgres://warden:warden@localhost:5432/warden up
WARDEN_TEST_DATABASE_URL=postgres://warden:warden@localhost:5432/warden uv run pytest
```

The schema has no foreign keys by design — the repository layer owns
referential integrity (e.g. `save(force=True)` deletes junction rows before
parent rows). Table relations:

```
roles.id      <- member_roles.role_id
members.id    <- member_roles.member_id
```

## Docker

```bash
make docker-build
make docker-run   # reads DISCORD_TOKEN from .env
```

Multi-stage build (`Dockerfile`): dependencies are installed in a `builder`
stage, the runtime stage copies only the built venv, `warden/` and `main.py`
— no `uv`, no build tools, no audio/voice libs in the final image. Runs
headless as a non-root user, timezone pinned to `Asia/Jakarta`. The image
does not carry `migrations/` — migrations are applied by a separate process
before the bot starts.

## Adding a feature

One feature = one folder under `warden/features/`, laid out like `ping/`:

```
warden/features/greet/
    __init__.py                     wiring: setup(bot) builds the deps and adds the cog
    handlers/greet_handler.py       the Cog — Discord in, Discord out
    services/protocol.py            what the handler depends on
    services/greet_service.py       the implementation
```

The folder is discovered and loaded automatically — there is no registry to
edit, so two people adding features never conflict. The only requirement is
`setup(bot)` in the feature's `__init__.py`:

```python
# warden/features/greet/__init__.py
from discord.ext import commands

from warden.features.greet.handlers.greet_handler import GreetHandlers
from warden.features.greet.services.greet_service import GreetService


async def setup(bot: commands.Bot) -> None:  # required, or the folder never loads
    await bot.add_cog(GreetHandlers(bot, GreetService()))
```

Handlers take services as constructor arguments, typed against the protocol —
that keeps the service testable without booting a bot. Onboarding adds two
more layers on the same idea: `repositories/` (persistence, SQL lives here
only) and `entities/` (plain data shapes passed between layers). Services
depend on repository protocols, never on a concrete database.

## Onboarding feature

Snapshots every member and their roles the first time the bot joins a guild
(point-in-time baseline — it is not kept in sync afterwards):

- **Bot joins a new guild** → auto-snapshot, one database transaction.
- **Bot is kicked and re-invited** → existing snapshot is kept, no re-snapshot.
- **`!onboard existing`** (requires *Manage Server*) → snapshot manually, e.g.
  if the feature was disabled when the bot joined.
- **`!onboard existing --force`** → replace the guild's snapshot.

`@everyone` is never stored (everyone has it, it carries no information).

## Registration feature

Manual member verification.

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

### Registration — desain

Alur pendaftaran & verifikasi member baru: orang masuk server, mengisi form di
private thread, lalu diverifikasi manual oleh orang dalam sebelum dapat role.

Fitur baru di `warden/features/registration/`. **Bukan** kelanjutan
`warden/features/onboarding/` — yang itu memotret member+role sekali saat bot
join, nol irisan dengan alur ini.

#### Alur

```
#registration-locket (publik, permanen)
  └─ [Onboard Me]
       └─ private thread per orang (invitable=False, auto_archive=60)
            └─ [Mahasiswa] / [Alumni]
                 └─ modal form
                      └─ submit → state=pending, auto_archive naik ke 7 hari
                           └─ kartu review → #registration-report
                                └─ [Approve] [Reject] [Join Thread]
```

**Approve** → role tipe + role prodi → nickname → pesan hasil ke thread → kartu
diedit di tempat, button disabled.

**Reject** → modal alasan → alasan diposting ke thread → `state=rejected`.
Orangnya boleh mendaftar ulang dari nol.

#### State

Satu baris `registrations` per **percobaan**, bukan per orang.

| State | Artinya | Klik Onboard Me lagi → |
|---|---|---|
| *(tidak ada baris aktif)* | belum pernah, atau semua percobaan terakhirnya ditolak | bikin thread baru |
| `open` | thread hidup, form belum disubmit | pakai thread lama, `add_user` lagi, balas ephemeral berisi link |
| `pending` | sudah submit, nunggu verifikator | ephemeral: "tunggu review" |
| `approved` | lolos | ephemeral: "sudah terverifikasi" |
| `rejected` | ditolak | diperlakukan seperti orang baru |

Sumber kebenaran = DB, bukan hasil scan thread di Discord. Thread yang sudah
ter-archive tidak ikut ter-list, jadi idempotensi berbasis API bocor persis di
kasus yang paling sering.

Semua balasan button ke pendaftar **ephemeral** — `#registration-locket` publik
dan pesan permanennya jangan ketimbun.

#### Schema

Satu tabel, kolom nullable, bentuk per-tipe dijaga `CHECK`. Ikut gaya
`migrations/20260822000000_init.sql`: tanpa FK, `GENERATED ALWAYS AS IDENTITY`.

```sql
CREATE TABLE registrations (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id          BIGINT NOT NULL,
    user_id           BIGINT NOT NULL,
    type              TEXT NOT NULL,          -- mahasiswa | alumni
    nama              TEXT NOT NULL,
    nama_panggilan    TEXT NOT NULL,
    nim               TEXT,                   -- wajib mahasiswa, opsional alumni
    angkatan          TEXT NOT NULL,
    prodi             TEXT,                   -- mahasiswa saja, key mapping env
    linkedin          TEXT,                   -- alumni saja
    state             TEXT NOT NULL,          -- open | pending | approved | rejected
    thread_id         BIGINT,
    report_message_id BIGINT,
    reject_reason     TEXT,
    expires_at        timestamptz,            -- TTL, hanya relevan saat state=open
    reviewed_by       BIGINT,
    reviewed_at       timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT registrations_shape CHECK (
        (type = 'mahasiswa' AND nim IS NOT NULL AND prodi IS NOT NULL)
     OR (type = 'alumni'    AND linkedin IS NOT NULL)
    )
);

-- satu orang cuma boleh punya satu registrasi hidup/lolos
CREATE UNIQUE INDEX registrations_active
    ON registrations (guild_id, user_id)
    WHERE state IN ('open', 'pending', 'approved');

-- satu NIM cuma boleh dimiliki satu registrasi yang approved.
-- NULL tidak pernah bentrok di Postgres → NIM alumni yang kosong aman gratis.
CREATE UNIQUE INDEX registrations_nim_approved
    ON registrations (guild_id, nim)
    WHERE state = 'approved' AND nim IS NOT NULL;
```

`angkatan` disimpan `TEXT` — identitas, bukan angka yang dihitung. Konsisten
dengan `joined_at TEXT` di tabel `members`.

Integritas dijaga database, bukan `if` di service: verifikator bisa mengklik
approve pada dua kartu hampir bersamaan, dan pemeriksaan di kode balapan.

#### Form

Modal maksimum 5 komponen — dua-duanya sudah mentok, tidak ada ruang tersisa.
`discord.py` 2.7.1 mendukung `Select` di dalam modal lewat `ui.Label`
(`discord/ui/modal.py:231`), jadi prodi tidak butuh langkah pilih terpisah.

| Mahasiswa | Alumni |
|---|---|
| Nama `max_length=32` | Nama `max_length=32` |
| Nama Panggilan `max_length=24` | Nama Panggilan `max_length=24` |
| NIM `min=max=8` | NIM `required=False` |
| Angkatan `min=max=4` | Angkatan `min=max=4` |
| Prodi `Select` (opsi = key mapping env) | LinkedIn |

Validasi didorong ke batasan bawaan Discord — kalau modal ditolak setelah
submit, ketikan orangnya hilang, dan modal tidak bisa merespons modal.

Yang tersisa di kode, satu pemeriksaan:

```python
if not angkatan.isdigit() or not 2000 <= int(angkatan) <= datetime.now().year:
    ...  # ephemeral + button "Isi Ulang" yang membuka modal dengan default= nilai lama
nim = nim.strip().upper()   # tanpa ini registrations_nim_approved bocor
```

Format LinkedIn sengaja **tidak** divalidasi. Regex URL selalu salah di sisi
yang bikin repot, dan verifikator toh membukanya.

#### Nickname

Format `[<PRODI>]<nama_panggilan>` — mahasiswa `[D3-TI]Rizky`, alumni
`[ALUMNI]Rizky`. Prodi = key mapping env di-`upper()`, supaya tidak ada tabel
nama tampilan kedua yang harus dijaga sinkron.

Batas nickname Discord 32 karakter: `[ALUMNI]` (8) + `max_length=24` = pas, tidak
pernah terpotong di kasus mana pun.

```python
with contextlib.suppress(discord.Forbidden):
    await member.edit(nick=nick)
```

Gagal ganti nickname **tidak boleh** membatalkan approve — role adalah hasil yang
penting. Nickname pemilik server tidak bisa diubah bot, apa pun permission-nya.

**Menguncinya = permission, bukan kode.** Cabut `Change Nickname` dari
`@everyone`; bot yang punya `Manage Nicknames` tetap bisa. Jangan pakai listener
`on_member_update` yang mengembalikan nickname — itu bot berkelahi dengan user,
jalan di tiap update member, dan yang paling sering kena malah mod yang sengaja
mengganti nama seseorang.

#### Otorisasi

**Button di Discord bisa diklik siapa pun yang bisa melihat pesannya.** Tidak ada
permission per-button, dan `@commands.has_guild_permissions(...)` — yang dipakai
di `onboarding_handler.py` — **tidak berlaku** untuk callback `ui.Button`.

```python
def is_verifier(self, user: discord.Member) -> bool:
    return (
        user.guild_permissions.manage_guild          # owner/admin selalu boleh
        or any(r.id == self.config.verifier_role_id for r in user.roles)
    )
```

Diperiksa di **setiap** callback (Approve, Reject, Join Thread), gagal → ephemeral.
Membatasi siapa yang bisa melihat `#registration-report` adalah lapisan kedua,
bukan pengaman — permission channel gampang tergeser diam-diam, kode tidak.

`reviewed_by` / `reviewed_at` wajib diisi. Verifikasi identitas adalah keputusan
yang suatu saat dipertanyakan; "siapa yang meloloskan orang ini" harus punya
jawaban.

#### Persistent view

Semua button `timeout=None` + `custom_id` statis, didaftarkan sekali di
`setup(bot)`. Tanpa ini, restart bot membuat semua button lama membalas
*"This interaction failed"* — pesannya tetap terlihat normal, jadi baru ketahuan
setelah ada yang komplain.

```python
bot.add_view(OnboardMeView())     # registration:start
bot.add_view(PilihTipeView())     # registration:mahasiswa | registration:alumni
bot.add_view(ReviewView())        # registration:approve | reject | join
```

`add_view` mendaftarkan handler untuk `custom_id`, bukan untuk satu pesan — satu
pendaftaran menghidupkan kembali seluruh thread lama dan semua kartu review yang
belum diputuskan.

**Nol state di dalam `custom_id`.** `custom_id` dikirim oleh klien; menitipkan
`user_id` di sana berarti mempercayai angka dari luar. Pakai `interaction.user.id`
(dari Discord, tidak bisa dipalsukan) dan `interaction.message.id` → lookup
`report_message_id`.

Pesan permanen di locket diposting lewat satu command admin (`Manage Server`)
yang **mengedit** pesan lama kalau dijalankan lagi, bukan memposting yang kedua.

#### TTL & cleanup

TTL 15 menit adalah **petunjuk cleanup, bukan gerbang**. `auto_archive_duration`
Discord hanya menerima 60/1440/4320/10080 menit, jadi 15 menit tidak bisa
dititipkan ke Discord dan harus jadi logika sendiri.

- Klik button, baris `open` sudah lewat `expires_at` → hapus thread lama, bikin
  baru, reset `expires_at`
- Submit di menit ke-20 dengan thread masih hidup → **tetap diterima**. Menolaknya
  hanya membuat orang yang sudah mengetik NIM kehilangan ketikannya; nol keuntungan.

Sapuan menghapus thread yang sudah ter-archive:

```python
@tasks.loop(hours=1)   # jalan sekali juga saat startup
async def sweep_archived(self) -> None:
    locket = self.bot.get_channel(self.config.locket_channel_id)
    async for thread in locket.archived_threads(private=True, limit=50):
        reg = await self.service.registration_by_thread(thread.id)
        if reg is None or reg.state == "pending":
            continue                    # bukan punya kita, atau masih nunggu verifikator
        await thread.delete()
        await self.service.clear_thread(thread.id)
```

- **`pending` tidak pernah disentuh** — verifikator manusia lambat, dan hasilnya
  butuh tempat untuk disampaikan.
- `limit=50` per pass: delete thread itu operasi channel-delete yang rate limit-nya
  galak. Sisanya kebagian jam berikutnya, tidak ada yang mendesak.
- `owns_thread` wajib — jangan hapus semua archived private thread di channel itu.
- `archived_threads(private=True)` butuh **bot** punya `Manage Threads`.

Bukan `on_thread_update`: auto-archive tidak dijamin memancarkan gateway event,
dan thread yang ter-archive saat bot mati tidak akan pernah dapat event susulan.
Sapuan berkala sudah mencakup keduanya dengan satu potong kode.

Approve/reject yang datang saat thread sudah ter-archive:

```python
await thread.edit(archived=False)
await thread.send(...)
```

#### Kartu review

```
┌─ Registrasi Mahasiswa · Percobaan ke-1
│ @rizky_  (id: 123456789)
│
│ Nama            Muhammad Rizky Ramadhan
│ Nama Panggilan  Rizky
│ NIM             A1B2C3D4
│ Angkatan        2021
│ Prodi           d3-ti
│
│ Akun dibuat     12 Mar 2021    Gabung server  20 Agu 2026
│ Disubmit        23 Agu 2026 14:03
└─ [ Approve ]  [ Reject ]  [ Join Thread ]
```

Yang wajib menonjol:

- **⚠️ NIM sudah dipakai @user_lain** — supaya ketahuan sebelum diklik, bukan
  setelah ditolak database
- **Percobaan ke-N** — pola "ditolak 4× dengan NIM berubah-ubah" hanya terlihat
  kalau angkanya dicetak
- **Umur akun Discord** (`member.created_at`) — satu-satunya sinyal alt account
  yang tersedia. Tampilkan tanggalnya, jangan bikin aturan otomatis.
- **Mention `@user`** supaya profilnya bisa dibuka, plus `user_id` mentah karena
  mention tidak berguna kalau orangnya sudah keluar server

Setelah diputuskan kartunya **diedit di tempat**, bukan dihapus: warna berubah,
footer jadi `Disetujui oleh @verifikator · 23 Agu 15:10`, ketiga button
`disabled=True`. `#registration-report` jadi log keputusan yang bisa digulir.

Dua verifikator mengklik bersamaan → yang kalah dapat `UniqueViolationError` dari
`registrations_active`, ditangkap, dibalas ephemeral *"sudah diputuskan oleh @x"*.

#### Join Thread

Bot yang memasukkan verifikator, **bukan** verifikator yang punya `Manage Threads`:

```python
reg = await self.service.by_report_message(interaction.message.id)
thread = interaction.guild.get_thread(reg.thread_id)
await thread.add_user(interaction.user)
await interaction.response.send_message(thread.jump_url, ephemeral=True)
```

`Manage Threads` jauh lebih besar dari kebutuhannya — dia membuka hak menghapus,
mengunci, dan meng-archive thread apa pun di seluruh server, plus melihat semua
private thread termasuk urusan moderasi. `add_user` memberi akses tepat satu
thread, dan cakupannya ditentukan kode, bukan setting yang bisa tergeser.

#### Config

Env var, satu instance bot per komunitas. `guild_id` tetap disimpan di tabel
supaya pintu multi-guild tidak tertutup.

```python
registration_enabled: bool                    # REGISTRATION_ENABLED, default true
registration_locket_channel_id: int
registration_report_channel_id: int
registration_verifier_role_id: int
registration_mahasiswa_role_id: int
registration_alumni_role_id: int
registration_prodi_roles: dict[str, int]      # d3-ti:333,d3-tk:444,s1-ml:555
```

```python
def _parse_role_map(raw: str) -> dict[str, int]:
    return {k: int(v) for k, v in (p.split(":", 1) for p in raw.split(",") if p)}
```

Pakai `os.environ[...]` untuk yang wajib, konsisten dengan `DISCORD_TOKEN` — fitur
ini mati total tanpa channel ID-nya, jadi lebih baik gagal saat startup daripada
hidup normal lalu diam saat mahasiswa pertama mengklik.

Bukan tabel `guild_settings`: itu menarik cache, invalidasi, command set/get, dan
yang paling repot — perilaku saat belum dikonfigurasi. Env var membuat cabang itu
tidak pernah ada.

Bukan pencocokan berdasarkan **nama** role: nama role diubah orang, dan pemetaan
berhenti bekerja tanpa satu pun error. Bukan JSON di env: kutip dan escape di
`.env`/`docker-compose.yml` tidak sebanding dengan yang dibeli.

Prodi wajib jadi **pilihan tertutup** yang nilainya persis key mapping. Kalau
bebas ketik, "D3 TI" lolos verifikasi tapi tidak dapat role prodi — gagal senyap.

Key yang tidak ada di mapping saat approve harus **menggagalkan approve** dengan
ephemeral yang jelas, bukan diam-diam hanya memberi role mahasiswa.

#### Permission yang harus diset di server

| Siapa | Permission |
|---|---|
| Bot | `Manage Threads`, `Manage Roles`, `Manage Nicknames` |
| Bot | role bot harus **di atas** semua role yang diberikan |
| `@everyone` | **cabut** `Change Nickname` |
| Role verifikator | **tanpa** `Manage Threads` |
| `#registration-report` | batasi yang bisa melihat (lapisan kedua) |

Dua kegagalan senyap yang paling mungkin di produksi:

1. Role bot di bawah role target → `add_roles` lempar `Forbidden`, approve terlihat
   sukses di UI tapi orangnya tidak dapat role. Tangkap `Forbidden` eksplisit dan
   balas ephemeral ke verifikator.
2. Orangnya sudah keluar server saat verifikator klik approve besoknya →
   `guild.get_member(...)` balik `None`. Tandai `approved` di DB, beri tahu
   verifikator, role menyusul lewat `on_member_join` yang mengecek `registrations`.
   Ini sekaligus jawaban gratis untuk orang yang keluar-masuk server.

#### Sengaja tidak dibangun

| Apa | Kapan ditambahkan |
|---|---|
| Crawler PDDikti | verifikasi manual dulu; nanti masuk sebagai **anotasi** di kartu review, bukan pengambil keputusan |
| Kolom `pddikti_*` | bersamaan crawler-nya — satu file migrasi goose, lebih murah daripada menebak sekarang |
| Tabel `guild_settings` | kalau benar ada guild kedua dengan channel berbeda |
| Batas jumlah percobaan | kalau benar ada spam; sekarang cukup cetak nomor percobaan di kartu |
| Role per-prodi untuk alumni | slot modal alumni sudah penuh, ada yang harus keluar |
| Role per-angkatan | datanya sudah di Postgres; role hanya masuk akal untuk permission atau mention |
| Sweeper event-driven | sapuan berkala sudah mencakupnya |
| Validasi format LinkedIn | verifikator membukanya sendiri |

#### Catatan operasional

`statement_cache_size=0` pada `create_pool()` belum dipasang. Aman di pgbouncer
`session` mode (default) yang dipakai sekarang. **Pecah** kalau nanti pindah ke
`transaction` mode — `asyncpg` memakai prepared statement per-koneksi, dan
pgbouncer memberi koneksi server berbeda tiap transaksi:

```
prepared statement "__asyncpg_stmt_3__" does not exist
```

Muncul sesekali, di bawah beban, dan tidak pernah kena di lokal tanpa pgbouncer.
Berlaku juga untuk pool yang sudah ada di
`warden/features/onboarding/__init__.py:19`.

Pindah ke `transaction` mode adalah langkah yang biasa diambil justru saat koneksi
mulai sesak — jadi ini menunggu di jalur pertumbuhan, bukan di pinggir.

## AI harness

This repo carries a graphify knowledge graph (`graphify-out/`) and Serena
project memories (`.serena/memories/`) for AI coding assistants. `.graphifyignore`
keeps the graph scoped to `warden/` source only — no docs/config noise.

- `make update-harness` — refresh the graph (code-only, no viz) and clear
  Serena's stale symbol cache. Safe to run anytime.
- `make install-hooks` — opt in to two git hooks:
  - `pre-commit` keeps `graphify-out/` out of code commits (unstages it when
    mixed with other paths).
  - `post-commit` does the same refresh automatically after each commit. It only
    runs when the commit touched `*.py`, and always lands the refreshed graph as
    its own separate commit (`chore(graphify): refresh graph`) on top of your
    code commit — all graphify changes, never mixed in.
