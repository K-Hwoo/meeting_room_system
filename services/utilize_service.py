import sqlite3
import datetime
import json

from datetime import datetime
from utils.server_setting import VALID_CATEGORIES
from utils.format_tools import parse_date_only, parse_hhmm

"""
회의실 예약 일정을 확인 후 그 날의 빈 시간 목록을 알려줌
- 空いている時間帯の検索
- 特定の日に duration_minutes 以上空いている時間帯をすべて探して返す。
"""
def find_available_slots(
    conn: sqlite3.Connection, date: str, duration_minutes: int,
    business_start: str, business_end: str,
) -> dict:

    target_date = parse_date_only(date)
    
    if target_date is None:
        return {
            "success": False, 
            "error": "invalid_date_format", 
            "given": date,
        }

    if not isinstance(duration_minutes, int) or duration_minutes <= 0:
        return {
            "success": False, 
            "error": "invalid_duration", 
            "given": duration_minutes,
        }

    start_min = parse_hhmm(business_start)
    end_min = parse_hhmm(business_end)
    
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
        (target_date, target_date),
    ).fetchall()

    def _to_minutes(dt_str: str) -> int:
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.hour * 60 + dt.minute

    # Business Hours 범위에서 회의실 예약 일정이 있는 구간을 찾음
    busy = []
    for r in rows:
        s = max(start_min, _to_minutes(r["start_time"]))
        e = min(end_min, _to_minutes(r["end_time"]))
        if s < e:
            busy.append((s, e))
    busy.sort()

    # 예약이 비어 있는 구간을 계산
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
        {
            "start": _to_hhmm(s), 
            "end": _to_hhmm(e), 
            "duration_minutes": e - s
         }
        for s, e in gaps
        if (e - s) >= duration_minutes
    ]

    return {
        "success": True, 
        "date": target_date, 
        "duration_minutes": duration_minutes, 
        "available_slots": available
    }


# 회의실 예약 관련 통계를 만든다
def get_statistics(
    conn: sqlite3.Connection, 
    start_date: str = None, end_date: str = None, 
    category: str = None,
) -> dict:

    """
    start_date, end_date: 'YYYY-MM-DD'。両方省略すると全期間が対象。
    category: 特定のカテゴリだけに絞りたい場合。

    統計:
    - by_category: カテゴリ別件数
    - by_category_percent: カテゴリ別割合(%)
    - by_weekday: 曜日別件数(月〜日)
    - by_hour: 開始時刻の時間帯別件数("09:00"など)
    - daily_counts: 日付別件数の推移(グラフの折れ線用)
    - average_duration_minutes: 平均所要時間(分)
    """
    query = "SELECT * FROM reservations WHERE 1=1"
    params = []

    # resolve --- 적용 가능 하지않나?
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

        s = datetime.datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
        e = datetime.datetime.strptime(r["end_time"], "%Y-%m-%d %H:%M:%S")

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