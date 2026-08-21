-- PRAGMA foreign_keys = ON;

-- ------------------------------------------------
-- rooms: 会議室のリスト
-- ------------------------------------------------

-- CREATE TABLE IF NOT EXISTS rooms (
--     id          INTEGER PRIMARY KEY AUTOINCREMENT,
--     name        TEXT NOT NULL,        -- 会議室の名
--     created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
-- );

-- ------------------------------------------------
-- reservations: 予約リスト
-- ------------------------------------------------

CREATE TABLE IF NOT EXISTS reservations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    -- room_id      INTEGER NOT NULL,    -- 会議室
    title        TEXT NOT NULL,       -- 予定のタイトル
    start_time   DATETIME NOT NULL,   -- 開始時間
    end_time     DATETIME NOT NULL,   -- 終了時間
    category     TEXT NOT NULL,       -- カテゴリー
    description  TEXT,                -- 簡単な説明
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 
    -- FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
 
    -- 終了時間が開始時間より早くなる誤入力を防止
    CHECK (end_time > start_time),
 
    -- カテゴリーは下の４つの値だけ許容(判断はClaudeが行う)
    CHECK (category IN ('会議', '接客', '面接', '自由'))
);

-- ------------------------------------------------
-- 会議室1室登録
-- ------------------------------------------------
-- INSERT INTO rooms (name)
-- SELECT 'Meeting_Room_101'
-- WHERE NOT EXISTS (SELECT 1 FROM rooms);