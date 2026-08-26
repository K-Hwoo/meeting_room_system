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
-- employees: 社員情報
-- ------------------------------------------------

CREATE TABLE IF NOT EXISTS employees (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,              -- 名前
    email       TEXT NOT NULL UNIQUE,       -- メールアドレス
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);


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
    -- 実は、CRUDはClaudeがしてくれるので、いらないかもしれない。   
 
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


-- ------------------------------------------------
-- 会議室1室登録
-- ------------------------------------------------
-- INSERT INTO rooms (name)
-- SELECT 'Meeting_Room_101'
-- WHERE NOT EXISTS (SELECT 1 FROM rooms);

-- ------------------------------------------------
-- 社員データ
-- ------------------------------------------------

INSERT OR IGNORE INTO employees (name, email)
VALUES
    ('田中太郎', 'tanaka@example.com'),
    ('山田花子', 'yamada@example.com'),
    ('佐藤健', 'sato@example.com');


-- ------------------------------------------------
-- 予約データ
-- ------------------------------------------------

INSERT INTO reservations
    (title, start_time, end_time, category, description)
VALUES
    (
        'プロジェクト進捗会議',
        '2026-08-27 10:00:00',
        '2026-08-27 11:00:00',
        '会議',
        'プロジェクトの進捗確認と今後のスケジュールについて話し合う'
    ),
    (
        '採用面接',
        '2026-08-27 14:00:00',
        '2026-08-27 15:00:00',
        '面接',
        'エンジニア候補者との面接'
    );


-- ------------------------------------------------
-- 予約と参加社員の関連
-- ------------------------------------------------

-- プロジェクト進捗会議
-- 参加者: 田中太郎、山田花子、佐藤健

INSERT INTO reservation_participants
    (reservation_id, employee_id)
SELECT
    r.id,
    e.id
FROM reservations r
CROSS JOIN employees e
WHERE r.title = 'プロジェクト進捗会議'
  AND e.email IN (
      'tanaka@example.com',
      'yamada@example.com',
      'sato@example.com'
  );


-- 採用面接
-- 参加者: 田中太郎、山田花子

INSERT INTO reservation_participants
    (reservation_id, employee_id)
SELECT
    r.id,
    e.id
FROM reservations r
CROSS JOIN employees e
WHERE r.title = '採用面接'
  AND e.email IN (
      'tanaka@example.com',
      'yamada@example.com'
  );