-- +goose Up
-- Filter chat: keyword + regex, hasilnya jadi corpus training fastText.
-- Tanpa FK, sama seperti 20260822000000_init.sql.
--   moderation_hits.id <- moderation_hit_matches.hit_id
--   moderation_keywords.id / moderation_regex_rules.id <- moderation_hit_matches.rule_id
--
-- Keyword dan regex sengaja tanpa guild_id: daftar kata ini properti bahasa
-- (ID/EN), bukan properti komunitas. Satu instance = satu komunitas.
CREATE TABLE moderation_keywords (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label      TEXT NOT NULL,
    term       TEXT NOT NULL,          -- seperti yang diketik, untuk ditampilkan
    normalized TEXT NOT NULL,          -- yang dicocokkan automaton
    enabled    BOOLEAN NOT NULL DEFAULT true,
    created_by BIGINT,
    created_at timestamptz NOT NULL DEFAULT now(),
    -- bukan partial index: remove itu soft, jadi baris nonaktif harus tetap
    -- bentrok supaya re-add bisa memakainya lewat ON CONFLICT DO UPDATE
    UNIQUE (label, normalized)
);

CREATE TABLE moderation_regex_rules (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label      TEXT NOT NULL,
    pattern    TEXT NOT NULL,
    target     TEXT NOT NULL DEFAULT 'raw',   -- raw | normalized
    note       TEXT,
    enabled    BOOLEAN NOT NULL DEFAULT true,
    created_by BIGINT,                        -- NULL = seed bawaan migration ini
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (label, pattern),
    CONSTRAINT moderation_regex_target CHECK (target IN ('raw', 'normalized'))
);

-- Satu baris per pesan yang kena. `content` disimpan permanen: inilah data
-- latih fase fastText. Lihat docs/configuration.md soal privasinya.
CREATE TABLE moderation_hits (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id   BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    author_id  BIGINT NOT NULL,
    content    TEXT NOT NULL,
    normalized TEXT NOT NULL,
    source     TEXT NOT NULL,          -- create | edit
    enforced   BOOLEAN NOT NULL,       -- pesannya jadi dihapus?
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT moderation_hits_source CHECK (source IN ('create', 'edit'))
);

CREATE INDEX moderation_hits_author  ON moderation_hits (guild_id, author_id);
CREATE INDEX moderation_hits_message ON moderation_hits (message_id);

-- Satu baris per kecocokan, bukan per pesan: satu pesan bisa kena banyak label
-- sekaligus. Bentuk ini yang bikin export multi-label fastText jadi satu
-- GROUP BY, dan mesinnya boleh tetap single-label di fase 1.
CREATE TABLE moderation_hit_matches (
    hit_id       BIGINT NOT NULL,      -- moderation_hits.id
    label        TEXT NOT NULL,
    rule_kind    TEXT NOT NULL,        -- keyword | regex
    rule_id      BIGINT,
    -- salinan, bukan lookup: rule boleh dihapus tanpa membuat hit lama
    -- kehilangan alasannya
    matched_term TEXT NOT NULL,
    CONSTRAINT moderation_hit_matches_kind CHECK (rule_kind IN ('keyword', 'regex'))
);

CREATE INDEX moderation_hit_matches_hit   ON moderation_hit_matches (hit_id);
CREATE INDEX moderation_hit_matches_label ON moderation_hit_matches (label);

-- Seed regex. Hanya pola BERSTRUKTUR — URL, angka, alamat wallet, nama situs
-- bergenerasi. Kata literal ('bokep', 'maxwin', 'anjing') bukan urusan regex,
-- itu keyword, dan tabel keyword sengaja dibiarkan kosong.
-- negative/bullying/sara tidak dapat seed sama sekali: tidak ada pola di sana.
INSERT INTO moderation_regex_rules (label, pattern, target, note) VALUES
    ('judol',  '\b[a-z]{3,12}(?:88|89|77|99|303|138|168|4d|slot)\b', 'normalized', 'Nama situs judol berangka: hoki88, dewa303, zeus4d. Berisik terhadap nickname/nama game.'),
    ('judol',  '\brtp\s*(?:live|slot|gacor)?\s*\d{2,3}\s*%', 'normalized', 'RTP live 98%'),
    ('judol',  '\b(?:situs|link|daftar|bandar|agen)\s+(?:slot|togel|judi|casino)\b', 'normalized', 'Ajakan daftar situs'),
    ('judol',  '\b(?:depo|depos?it|wd)\s*\d+\s*(?:k|rb|ribu|jt)?\b', 'normalized', 'depo 10k, wd 500rb'),
    ('scam',   '\b(?:discord\.(?:gg|com/invite)|dsc\.gg)/[\w-]+', 'raw', 'Undangan ke server lain'),
    ('scam',   '\b(?:bit\.ly|tinyurl\.com|s\.id|cutt\.ly|shorturl\.at|is\.gd|linktr\.ee)/\S+', 'raw', 'Pemendek URL; sengaja tidak di-resolve, kehadirannya sendiri yang jadi sinyal'),
    ('scam',   '\b(?:free|gratis)\s*(?:nitro|discord\s*nitro|steam\s*gift|robux)\b', 'normalized', 'Umpan hadiah palsu'),
    ('scam',   '\b(?:wa|whatsapp|telp|hub(?:ungi)?)\W{0,3}(?:0|\+?62)8\d{7,11}\b', 'raw', 'Nomor WA + ajakan. Berisik terhadap orang yang jujur berbagi kontak.'),
    ('crypto', '\b0x[a-fA-F0-9]{40}\b', 'raw', 'Alamat ETH'),
    ('crypto', '\b(?:bc1|[13])[a-hj-np-z0-9]{25,62}\b', 'raw', 'Alamat BTC'),
    ('crypto', '\b(?:seed|recovery)\s*phrase\b|\bprivate\s*key\b', 'normalized', 'Umpan pencurian wallet'),
    ('porn',   '\b(?:t\.me|telegram\.me)/\S*(?:bokep|bo|vcs|18)\S*', 'raw', 'Kanal Telegram konten dewasa');

-- +goose Down
DROP TABLE moderation_hit_matches;
DROP TABLE moderation_hits;
DROP TABLE moderation_regex_rules;
DROP TABLE moderation_keywords;
