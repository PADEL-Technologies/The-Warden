-- +goose Up
-- Satu baris per percobaan pendaftaran, bukan per orang.
-- Tanpa FK, sama seperti 20260822000000_init.sql.
CREATE TABLE registrations (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id          BIGINT NOT NULL,
    user_id           BIGINT NOT NULL,             -- snowflake Discord
    type              TEXT,                        -- mahasiswa | alumni
    nama              TEXT,
    nama_panggilan    TEXT,
    nim               TEXT,                        -- wajib mahasiswa, opsional alumni
    angkatan          TEXT,                        -- identitas, bukan angka yang dihitung
    prodi             TEXT,                        -- mahasiswa saja, key mapping env
    linkedin          TEXT,                        -- alumni saja
    state             TEXT NOT NULL,               -- open | pending | approved | rejected
    thread_id         BIGINT,
    report_message_id BIGINT,
    reject_reason     TEXT,
    expires_at        timestamptz,                 -- TTL, hanya relevan saat state=open
    reviewed_by       BIGINT,
    reviewed_at       timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    -- state=open dibuat saat tombol diklik, sebelum formnya ada: semua kolom form
    -- masih NULL. Bentuk per-tipe baru berlaku setelah submit.
    CONSTRAINT registrations_shape CHECK (
        state = 'open'
     OR (nama IS NOT NULL AND nama_panggilan IS NOT NULL AND angkatan IS NOT NULL
         AND ((type = 'mahasiswa' AND nim IS NOT NULL AND prodi IS NOT NULL)
           OR (type = 'alumni'    AND linkedin IS NOT NULL)))
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

-- lookup dari interaction: thread_id untuk view di thread, report_message_id untuk kartu
CREATE INDEX registrations_thread ON registrations (thread_id);
CREATE INDEX registrations_report_message ON registrations (report_message_id);

-- +goose Down
DROP TABLE registrations;
