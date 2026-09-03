import sqlite3
import json
from datetime import datetime

DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
]

# 튜플로 반환되는 sqlite return 값을 딕셔너리화
def row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def parse_json_list(value) -> list:
    """SQLite TEXT에 저장된 JSON 배열을 Python list로 변환한다."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def reservation_row_to_dict(row: sqlite3.Row) -> dict:
    data = row_to_dict(row)
    
    if "participants" in data:
        data["participants"] = parse_json_list(data["participants"])
        
    return data


def resolve_date_range(date, start_date, end_date):
    # 날짜를 받으면 (날짜, 날짜) return
    if date is not None:
        return date, date

    # 받은게 전부 None 이면 (None, None) return (Error)
    if start_date is None and end_date is None:
        return None, None

    # start_date, end_date 처리
    # 두 값을 모두 정상적으로 받으면 각각 (range_start, range_end)로 return
    # start_date, end_date 중 하나만 받았을 경우에는 받은 값으로 (range_start, range_end)를 return
    range_start = start_date if start_date is not None else end_date
    range_end = end_date if end_date is not None else start_date
    return range_start, range_end


def parse_datetime(value: str):
    if not value:
        return None
    
    for fmt in DATETIME_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        
    return None


def parse_date_only(value: str):
    if not value:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        return None


def parse_hhmm(value: str):
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%H:%M")
        
        # minutes로 return
        return dt.hour * 60 + dt.minute
    except ValueError:
        return None