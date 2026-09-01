PRAGMA foreign_keys = ON;

-- ------------------------------------------------
-- employees: 社員情報
-- ------------------------------------------------

CREATE TABLE IF NOT EXISTS employees (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,              -- 名前
    email       TEXT NOT NULL UNIQUE,       -- メールアドレス
    is_admin    INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ------------------------------------------------
-- reservations: 会議室の予約リスト
-- ------------------------------------------------

CREATE TABLE IF NOT EXISTS reservations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,       -- 予定のタイトル
    start_time   DATETIME NOT NULL,   -- 開始時間
    end_time     DATETIME NOT NULL,   -- 終了時間
    category     TEXT NOT NULL,       -- カテゴリー
    description  TEXT,                -- 簡単な説明
    google_calendar_event_id  TEXT,   -- Googleカレンダーに探しやすいにするため
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 
    -- 終了時間が開始時間より早くなる誤入力を防止
    CHECK (end_time > start_time), 
 
    -- カテゴリーは下の４つの値だけ許容(判断はClaudeが行う)
    CHECK (category IN ('会議', '接客', '面接', '自由'))
);


-- ------------------------------------------------
-- reservation_participants:
-- 予約と社員の関係
-- ------------------------------------------------

CREATE TABLE IF NOT EXISTS reservation_participants (
    reservation_id  INTEGER NOT NULL,
    employee_id     INTEGER NOT NULL,

    PRIMARY KEY (reservation_id, employee_id),

    FOREIGN KEY (reservation_id)
        REFERENCES reservations(id)
        ON DELETE CASCADE,

    FOREIGN KEY (employee_id)
        REFERENCES employees(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reservation_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    start_time      DATETIME NOT NULL,
    end_time        DATETIME NOT NULL,
    category        TEXT NOT NULL,
    description     TEXT,
    requester_email TEXT NOT NULL,
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

-- 社員から参加している会議を検索するためのIndex
CREATE INDEX IF NOT EXISTS idx_participants_employee
ON reservation_participants(employee_id);

-- 会議から参加者を検索するためのIndex
CREATE INDEX IF NOT EXISTS idx_participants_reservation
ON reservation_participants(reservation_id);

-- 会議の時間から検索するためのIndex
CREATE INDEX IF NOT EXISTS idx_reservations_start_time
ON reservations(start_time);


-- ============================================================
-- Verification
-- ============================================================

SELECT
    id,
    name,
    email
FROM employees
ORDER BY id;

SELECT
    id,
    title,
    start_time,
    end_time,
    category,
    description
FROM reservations
ORDER BY start_time;

SELECT
    r.title AS meeting_title,
    r.start_time,
    e.name AS participant_name,
    e.email AS participant_email
FROM reservation_participants rp
JOIN reservations r
    ON rp.reservation_id = r.id
JOIN employees e
    ON rp.employee_id = e.id
ORDER BY r.start_time, e.id;