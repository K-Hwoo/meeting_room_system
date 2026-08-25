# すべての関数は dict を返します。
# {"success": True, ...} または {"success": False, "error": "..."}

import sqlite3
from datetime import datetime

VALID_CATEGORIES = ["会議", "接客", "面接", "自由"]

DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
]

def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def _parse_datetime(value: str):
    if not value:
        return None
    
    for fmt in DATETIME_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        
    return None

def _parse_date_only(value: str):
    """'YYYY-MM-DD' 形式のみ許容。失敗したら None。"""
    if not value:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        return None

def _parse_hhmm(value: str):
    """'HH:MM' 形式を分単位の整数に変換。失敗したら None。"""
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%H:%M")
        return dt.hour * 60 + dt.minute
    except ValueError:
        return None

def _row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


# ------------------------------------------------
# rooms
# ------------------------------------------------
 
# def list_rooms(conn: sqlite3.Connection) -> dict:
#     rows = conn.execute("SELECT * FROM rooms ORDER BY id").fetchall()
#     return {"success": True, "rooms": [_row_to_dictW(r) for r in rows]}

# def _room_exists(conn: sqlite3.Connection, room_id: int) -> bool:
#     row = conn.execute("SELECT 1 FROM rooms WHERE id = ?", (room_id,)).fetchone()
#     return row is not None
 
 
# ------------------------------------------------
# 重ねる予約チェック
# ------------------------------------------------
def _find_overlapping(conn, start_time, end_time, exclude_id=None) -> list:
    query = """
        SELECT * FROM reservations
        WHERE start_time < ?
          AND end_time > ?

    """
    params = [start_time, end_time] 
    
    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)

    rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


# ------------------------------------------------
# reservations - CRUD
# ------------------------------------------------
def add_reservation(
    conn: sqlite3.Connection,
    title: str,
    start_time: str,
    end_time: str,
    category: str,
    description: str = None,
) -> dict:
    # 必須項目確認
    missing = []
    if not title:
        missing.append("title")
    if not start_time:
        missing.append("start_time")
    if not end_time:
        missing.append("end_time")
    if not category:
        missing.append("category")
    if missing:
        return {"success": False, "error": "missing_fields", "missing_fields": missing}
 
    # # 使用可能な会議室があるか確認
    # if not _room_exists(conn, room_id):
    #     return {"success": False, "error": "room_not_found", "room_id": room_id}
 
 
    # ------------- 検証 -------------
    if category not in VALID_CATEGORIES:
        return {
            "success": False,
            "error": "invalid_category",
            "valid_categories": VALID_CATEGORIES,
            "given": category,
        }
 
    norm_start = _parse_datetime(start_time)
    norm_end = _parse_datetime(end_time)
    if norm_start is None or norm_end is None:
        return {
            "success": False,
            "error": "invalid_datetime_format",
            "expected_formats": DATETIME_FORMATS,
            "given": {"start_time": start_time, "end_time": end_time},
        }

    if norm_start >= norm_end:
        return {
            "success": False,
            "error": "end_before_start",
            "start_time": norm_start,
            "end_time": norm_end,
        }
        
    overlapping = _find_overlapping(conn, norm_start, norm_end)
    if overlapping:
        return {"success": False, "error": "time_overlap", "conflicts": overlapping}
 
    # 予約追加
    try:
        cur = conn.execute(
            """
            INSERT INTO reservations (title, start_time, end_time, category, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, norm_start, norm_end, category, description),
        )
        conn.commit()
        
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM reservations WHERE id = ?", (new_id,)).fetchone()
        return {"success": True, "reservation": _row_to_dict(row)}

    except sqlite3.IntegrityError as e:
        return {"success": False, "error": "db_constraint_failed", "detail": str(e)}
 
 
def update_reservation(conn: sqlite3.Connection, reservation_id: int, **fields) -> dict:
    # 入力されていないフィールドは既存の値を保持
    existing_row = conn.execute(
        "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
    ).fetchone()

    if existing_row is None:
        return {"success": False, "error": "reservation_not_found", "reservation_id": reservation_id}
 
    existing = _row_to_dict(existing_row)
 
    allowed = ["title", "start_time", "end_time", "category", "description"]
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
 
    new_title = updates.get("title", existing["title"])
    new_start = updates.get("start_time", existing["start_time"])
    new_end = updates.get("end_time", existing["end_time"])
    new_category = updates.get("category", existing["category"])
    new_description = updates.get("description", existing["description"])
 
    if "category" in updates and new_category not in VALID_CATEGORIES:
        return {
            "success": False,
            "error": "invalid_category",
            "valid_categories": VALID_CATEGORIES,
            "given": new_category,
        }
 
    if "start_time" in updates:
        norm_start = _parse_datetime(new_start)
        if norm_start is None:
            return {
                "success": False,
                "error": "invalid_datetime_format",
                "expected_formats": DATETIME_FORMATS,
                "given": {"start_time": new_start},
            }
    else:
        norm_start = new_start
 
    if "end_time" in updates:
        norm_end = _parse_datetime(new_end)
        if norm_end is None:
            return {
                "success": False,
                "error": "invalid_datetime_format",
                "expected_formats": DATETIME_FORMATS,
                "given": {"end_time": new_end},
            }
    else:
        norm_end = new_end
 
    if norm_start >= norm_end:
        return {
            "success": False,
            "error": "end_before_start",
            "start_time": norm_start,
            "end_time": norm_end,
        }

    # 重ねる予約確認（自身は除外）
    overlapping = _find_overlapping(conn, norm_start, norm_end, exclude_id=reservation_id)
    if overlapping:
        return {"success": False, "error": "time_overlap", "conflicts": overlapping}
 
    try:
        conn.execute(
            """
            UPDATE reservations
            SET title = ?, start_time = ?, end_time = ?, category = ?, description = ?
            WHERE id = ?
            """,
            (new_title, norm_start, norm_end, new_category, new_description, reservation_id),
        )
        conn.commit()
        
        row = conn.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
        return {"success": True, "reservation": _row_to_dict(row)}
    
    except sqlite3.IntegrityError as e:
        return {"success": False, "error": "db_constraint_failed", "detail": str(e)}
 

def delete_reservation(conn: sqlite3.Connection, reservation_id: int) -> dict:
    row = conn.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
    if row is None:
        return {"success": False, "error": "reservation_not_found", "reservation_id": reservation_id}
 
    conn.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    conn.commit()
    return {"success": True, "deleted": _row_to_dict(row)}
 
 
def list_reservations(
    conn: sqlite3.Connection,
    date: str = None,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
) -> dict:
    """
    data: 'YYYY-MM-DD' 形式。
    date: 'YYYY-MM-DD' 形式。該当日付にかかっている予約のみ (start_date/end_dateと同時使用不可)
    start_date, end_date: 'YYYY-MM-DD' 形式.その範囲と少しでも重なる予約すべて.
        両方を渡すと範囲指定、片方だけ渡すとその日付のみを対象とする.
        dateが渡されるとstart_date/end_dateよりもdateが優先される.
    category: 特定のカテゴリのみ (指定がない場合は全件)
    """
    query = "SELECT * FROM reservations WHERE 1=1"
    params = []
 
    # if room_id is not None:
    #     query += " AND room_id = ?"
    #     params.append(room_id)
 
    if date is not None:
        query += " AND date(start_time) <= date(?) AND date(end_time) >= date(?)"
        params.extend([date, date])
    elif start_date is not None or end_date is not None:
        range_start = start_date if start_date is not None else end_date
        range_end = end_date if end_date is not None else start_date
        query += " AND date(start_time) <= date(?) AND date(end_time) >= date(?)"
        params.extend([range_end, range_start])
 
    if category is not None:
        if category not in VALID_CATEGORIES:
            return {
                "success": False,
                "error": "invalid_category",
                "valid_categories": VALID_CATEGORIES,
                "given": category,
            }
        query += " AND category = ?"
        params.append(category)
 
    query += " ORDER BY start_time"
    rows = conn.execute(query, params).fetchall()
    
    return {"success": True, "reservations": [_row_to_dict(r) for r in rows]}


# ------------------------------------------------
# 空いている時間帯の検索
# ------------------------------------------------
def find_available_slots(
    conn: sqlite3.Connection,
    date: str,
    duration_minutes: int,
    business_start: str = "09:00",
    business_end: str = "18:00",
) -> dict:
    """
    特定の日に duration_minutes 以上空いている時間帯をすべて探して返す。

    date: 'YYYY-MM-DD'
    duration_minutes: 必要な最小所要時間(分)。1以上の整数。
    business_start, business_end: 営業時間、'HH:MM' 形式。この範囲内でのみ探索。
    """
    norm_date = _parse_date_only(date)
    if norm_date is None:
        return {"success": False, "error": "invalid_date_format", "given": date}

    if not isinstance(duration_minutes, int) or duration_minutes <= 0:
        return {"success": False, "error": "invalid_duration", "given": duration_minutes}

    start_min = _parse_hhmm(business_start)
    end_min = _parse_hhmm(business_end)
    if start_min is None or end_min is None or start_min >= end_min:
        return {
            "success": False,
            "error": "invalid_business_hours",
            "given": {"business_start": business_start, "business_end": business_end},
        }

    rows = conn.execute(
        """
        SELECT start_time, end_time FROM reservations
        WHERE date(start_time) <= date(?) AND date(end_time) >= date(?)
        ORDER BY start_time
        """,
        (norm_date, norm_date),
    ).fetchall()

    def _to_minutes(dt_str: str) -> int:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.hour * 60 + dt.minute

    # 営業時間の範囲内にクリッピングした busy 区間
    busy = []
    for r in rows:
        s = max(start_min, _to_minutes(r["start_time"]))
        e = min(end_min, _to_minutes(r["end_time"]))
        if s < e:
            busy.append((s, e))
    busy.sort()

    # 空き区間の計算
    gaps = []
    cursor = start_min
    for s, e in busy:
        if s > cursor:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < end_min:
        gaps.append((cursor, end_min))

    def _to_hhmm(m: int) -> str:
        return f"{m // 60:02d}:{m % 60:02d}"

    available = [
        {"start": _to_hhmm(s), "end": _to_hhmm(e), "duration_minutes": e - s}
        for s, e in gaps
        if (e - s) >= duration_minutes
    ]

    return {"success": True, "date": norm_date, "duration_minutes": duration_minutes, "available_slots": available}


# ------------------------------------------------
# 予約件数の集計
# ------------------------------------------------
def count_reservations(
    conn: sqlite3.Connection,
    date: str = None,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
) -> dict:
    """
    条件に合う予約件数を数える。パラメータの意味は list_reservations と同じ。
    全体件数(total)とカテゴリ別件数(by_category)を一緒に返す。
    """
    query = "SELECT category, COUNT(*) as cnt FROM reservations WHERE 1=1"
    params = []

    if date is not None:
        query += " AND date(start_time) <= date(?) AND date(end_time) >= date(?)"
        params.extend([date, date])
    elif start_date is not None or end_date is not None:
        range_start = start_date if start_date is not None else end_date
        range_end = end_date if end_date is not None else start_date
        query += " AND date(start_time) <= date(?) AND date(end_time) >= date(?)"
        params.extend([range_end, range_start])

    if category is not None:
        if category not in VALID_CATEGORIES:
            return {
                "success": False,
                "error": "invalid_category",
                "valid_categories": VALID_CATEGORIES,
                "given": category,
            }
        query += " AND category = ?"
        params.append(category)

    query += " GROUP BY category"
    rows = conn.execute(query, params).fetchall()

    by_category = {r["category"]: r["cnt"] for r in rows}
    total = sum(by_category.values())

    return {"success": True, "total": total, "by_category": by_category}


# ------------------------------------------------
# 詳細統計（グラフ化しやすい形式）
# ------------------------------------------------
def get_statistics(
    conn: sqlite3.Connection,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
) -> dict:
    """
    期間内の予約データから複数の統計をまとめて計算する。
    「グラフで見せて」「傾向を教えて」のような、単純な件数以上の分析が
    必要なときに使う(単純な件数だけなら count_reservations で十分)。

    start_date, end_date: 'YYYY-MM-DD'。両方省略すると全期間が対象。
    category: 特定のカテゴリだけに絞りたい場合。

    返す統計:
    - by_category: カテゴリ別件数
    - by_category_percent: カテゴリ別割合(%)
    - by_weekday: 曜日別件数(月〜日)
    - by_hour: 開始時刻の時間帯別件数("09:00"など)
    - daily_counts: 日付別件数の推移(グラフの折れ線用)
    - average_duration_minutes: 平均所要時間(分)
    """
    query = "SELECT * FROM reservations WHERE 1=1"
    params = []

    if start_date is not None or end_date is not None:
        range_start = start_date if start_date is not None else end_date
        range_end = end_date if end_date is not None else start_date
        query += " AND date(start_time) <= date(?) AND date(end_time) >= date(?)"
        params.extend([range_end, range_start])

    if category is not None:
        if category not in VALID_CATEGORIES:
            return {
                "success": False,
                "error": "invalid_category",
                "valid_categories": VALID_CATEGORIES,
                "given": category,
            }
        query += " AND category = ?"
        params.append(category)

    rows = conn.execute(query, params).fetchall()
    total = len(rows)

    if total == 0:
        return {
            "success": True,
            "total": 0,
            "by_category": {},
            "by_category_percent": {},
            "by_weekday": {},
            "by_hour": {},
            "daily_counts": {},
            "average_duration_minutes": 0,
        }

    weekday_labels = ["月", "火", "水", "木", "金", "土", "日"]
    by_category = {}
    by_weekday = {label: 0 for label in weekday_labels}
    by_hour = {}
    daily_counts = {}
    total_duration = 0.0

    for r in rows:
        cat = r["category"]
        by_category[cat] = by_category.get(cat, 0) + 1

        s = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
        e = datetime.strptime(r["end_time"], "%Y-%m-%d %H:%M:%S")

        by_weekday[weekday_labels[s.weekday()]] += 1

        hour_label = f"{s.hour:02d}:00"
        by_hour[hour_label] = by_hour.get(hour_label, 0) + 1

        date_label = s.strftime("%Y-%m-%d")
        daily_counts[date_label] = daily_counts.get(date_label, 0) + 1

        total_duration += (e - s).total_seconds() / 60

    by_category_percent = {k: round(v / total * 100, 1) for k, v in by_category.items()}

    return {
        "success": True,
        "total": total,
        "by_category": by_category,
        "by_category_percent": by_category_percent,
        "by_weekday": by_weekday,
        "by_hour": dict(sorted(by_hour.items())),
        "daily_counts": dict(sorted(daily_counts.items())),
        "average_duration_minutes": round(total_duration / total, 1),
    }