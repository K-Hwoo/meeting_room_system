import sqlite3
import json
from datetime import datetime

from utils.server_setting import VALID_CATEGORIES

DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
]


"""
튜플로 반환되는 sqlite return값을 딕셔너리화
列名をキー、行の値をバリューとするDictionaryを返します。
"""
def row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def parse_text_to_list(value) -> list:
    """
    SQLiteのTEXTに格納された値を
    Pythonのリストに変換します。
    """
    if value is None:
        return []
    
    # if isinstance(value, list):
    #     return value
    
    try:
        parsed = json.loads(value)
        
    except (TypeError, ValueError):
        return []
    
    return parsed if isinstance(parsed, list) else []


def get_reservation_data(row: sqlite3.Row) -> dict:
    data = row_to_dict(row)
    
    # if "participants" in data:
    data["participants"] = parse_text_to_list(data["participants"])
        
    return data

# ====================================================================

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


def validate_date_range(
    date: str = None,
    start_date: str = None,
    end_date: str = None,
) -> dict:
    """
    단일 날짜 또는 기간 입력을 검증하고
    최종 조회 시작일/종료일을 반환한다.
    """

    range_start, range_end = resolve_date_range(
        date,
        start_date,
        end_date,
    )

    # 날짜 조건 자체가 없는 경우
    if range_start is None and range_end is None:
        return {
            "success": True,
            "start_date": None,
            "end_date": None,
        }

    normalized_start = parse_date_only(range_start)
    normalized_end = parse_date_only(range_end)

    if normalized_start is None or normalized_end is None:
        return {
            "success": False,
            "error": "invalid_date_format",
            "expected": "YYYY-MM-DD",
            "given": {
                "date": date,
                "start_date": start_date,
                "end_date": end_date,
            },
        }

    if normalized_start > normalized_end:
        return {
            "success": False,
            "error": "invalid_date_range",
            "start_date": normalized_start,
            "end_date": normalized_end,
        }

    return {
        "success": True,
        "start_date": normalized_start,
        "end_date": normalized_end,
    }


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
    
# ====================================================================
def validate_category(category: str) -> dict:
    # 지정한 4개의 카테고리 이외의 것을 받으면 에러처리
    if category not in VALID_CATEGORIES:
        return {
            "success": False,
            "error": "invalid_category",
            "valid_categories": VALID_CATEGORIES,
            "given": category,
        }

    return {
        "success": True,
    }


def validate_reservation_input(
    title: str,
    start_time: str,
    end_time: str,
    category: str,
) -> dict:

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
        return {
            "success": False,
            "error": "missing_fields",
            "missing_fields": missing,
        }
    
    category_validation = validate_category(category)

    if not category_validation["success"]:
        return category_validation

    norm_start = parse_datetime(start_time)
    norm_end = parse_datetime(end_time)

    # norm_start랑 norm_end가 None이 들어가는 경우에는 에러처리
    # => Dify LLM으로부터 받은 날짜 형식에 문제가 있음을 나타냄
    if norm_start is None or norm_end is None:
        return {
            "success": False,
            "error": "invalid_datetime_format",
            "expected_formats": DATETIME_FORMATS,
            "given": {
                "start_time": start_time,
                "end_time": end_time,
            },
        }

    # 시작 시간이 종료 시간보다 뒤인 경우는 에러처리
    if norm_start >= norm_end:
        return {
            "success": False,
            "error": "end_before_start",
            "start_time": norm_start,
            "end_time": norm_end,
        }

    return {
        "success": True,
        "start_time": norm_start,
        "end_time": norm_end,
    }