PRAGMA foreign_keys = ON;

-- ------------------------------------------------
-- employees: 社員情報
-- ------------------------------------------------

CREATE TABLE IF NOT EXISTS employees (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ------------------------------------------------
-- reservations: 会議室の予約リスト
-- ------------------------------------------------

CREATE TABLE IF NOT EXISTS reservations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    start_time   DATETIME NOT NULL,
    end_time     DATETIME NOT NULL,
    category     TEXT NOT NULL,
    description  TEXT,
    participants TEXT NOT NULL DEFAULT '[]',
    google_calendar_event_id  TEXT,   -- Googleカレンダーに探しやすいにするため
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 
    -- 終了時間が開始時間より早くなる誤入力を防止
    CHECK (end_time > start_time), 
 
    -- カテゴリーは下の４つの値だけ許容(判断はClaudeが行う)
    CHECK (category IN ('会議', '接客', '面接', '自由'))
);


-- ------------------------------------------------
-- reservation_requests:
-- ------------------------------------------------
CREATE TABLE IF NOT EXISTS reservation_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    start_time      DATETIME NOT NULL,
    end_time        DATETIME NOT NULL,
    category        TEXT NOT NULL,
    description     TEXT,
    participant_names TEXT NOT NULL, 
    status          TEXT NOT NULL DEFAULT 'pending',
    reject_reason   TEXT,
    reservation_id  INTEGER,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE SET NULL,
    CHECK (end_time > start_time),
    CHECK (category IN ('会議', '接客', '面接', '自由')),
    CHECK (status IN ('pending', 'approved', 'rejected'))
);
CREATE INDEX IF NOT EXISTS idx_requests_status ON reservation_requests(status);

-- ============================================================
-- Index
-- ============================================================

-- 社員名で検索するためのIndex
CREATE INDEX IF NOT EXISTS idx_employees_name
ON employees(name);

-- 会議の時間から検索するためのIndex
CREATE INDEX IF NOT EXISTS idx_reservations_start_time
ON reservations(start_time);
