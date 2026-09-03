import sqlite3

from utils.server_setting import VALID_CATEGORIES
from utils.format_tools import reservation_row_to_dict, resolve_date_range 
from utils.format_tools import DATETIME_FORMATS, parse_datetime

from services import save_info_service
from utils import google_calendar

# 예약 희망하는 시간에 다른 회의실 예약이 있는지 체크
def find_overlapping(conn, start_time, end_time, exclude_id=None) -> list:
    query = """
        SELECT * FROM reservations
        WHERE start_time < ?
        AND end_time > ?
    """
    params = [end_time, start_time]
    
    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)

    rows = conn.execute(query, params).fetchall()
    return [reservation_row_to_dict(r) for r in rows]

# =============================================================================

"""
특정 날짜・기간 중 회의실 예약 상황 조회
特定の日付や期間中の会議室予約状況の確認
"""
def list_reservations(
    conn: sqlite3.Connection,
    date: str = None,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
) -> dict:

    query = "SELECT * FROM reservations WHERE 1=1"
    params = []
 
    range_start, range_end = resolve_date_range(date, start_date, end_date)

    # 해당 날짜 / 기간 필터링
    if range_start is not None or range_end is not None:
        query += " AND date(start_time) <= date(?) AND date(end_time) >= date(?)"
        params.extend([range_end, range_start])

    # 카테고리가 있다면 필터링
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
 
    query += " ORDER BY start_time, id"
    rows = conn.execute(query, params).fetchall()
    
    return {"success": True, "reservations": [reservation_row_to_dict(r) for r in rows]}


def create_reservation(
    conn: sqlite3.Connection, title: str, start_time: str, end_time: str,
    category: str, description: str = None,
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
            "missing_fields": missing
        }
 
 
    # 지정한 4개의 카테고리 이외의 것을 받으면 에러처리
    if category not in VALID_CATEGORIES:
        return {
            "success": False,
            "error": "invalid_category",
            "valid_categories": VALID_CATEGORIES,
            "given": category,
        }
 
    norm_start = parse_datetime(start_time)
    norm_end = parse_datetime(end_time)
    
    # norm_start랑 norm_end가 None이 들어가는 경우에는 에러처리
    # => Dify LLM으로부터 받은 날짜 형식에 문제가 있음을 나타냄
    if norm_start is None or norm_end is None:
        return {
            "success": False,
            "error": "invalid_datetime_format",
            "expected_formats": DATETIME_FORMATS,
            "given": {"start_time": start_time, "end_time": end_time},
        }

    # 시작 시간이 종료 시간보다 뒤인 경우는 에러처리
    if norm_start >= norm_end:
        return {
            "success": False,
            "error": "end_before_start",
            "start_time": norm_start,
            "end_time": norm_end,
        }
    
    # 해당 시간대에 겹치는 에러가 있으면 에러처리
    overlapping = find_overlapping(conn, norm_start, norm_end)
    if overlapping:
        return {
            "success": False, 
            "error": "time_overlap", 
            "conflicts": overlapping
        }


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
        
        # 회의실 예약 결과 반환
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM reservations WHERE id = ?", (new_id,)).fetchone()
        return {
            "success": True, 
            "reservation": reservation_row_to_dict(row)
        }

    except sqlite3.IntegrityError as e:
        return {
            "success": False, 
            "error": "db_constraint_failed", 
            "detail": str(e)
        }


def delete_reservation() :
    pass


def update_reservation() :
    pass


# MCP 서버용 회의실 일정 생성 통합 코드
def create_reservation_integrated(
    conn: sqlite3.Connection, title: str, start_time: str, end_time: str,
    category: str, participant: list, description: str = None, 
) -> dict:
    """
    예약을 생성하고, 참가자 연결 및 Google Calendar 동기화까지 수행한다.

    구글 캘린더 설정에 실패해도 예약 자체는 유지, 
    호출자는 calendar_sync와 calendar_error로 동기화 상태를 확인할 수 있다.
    """
    
    if not participant:
        return {
            "success": False,
            "error": "participants_required",
            "message": "participants must contain at least one employee."
        }
    
    # 참가자 제외한 정보 우선 저장
    result = create_reservation(
        conn, title, start_time, end_time, category, description
    )
    
    if not result["success"]:
        return result

    # 저장된 예약 일정 가져오기
    reservation = result["reservation"]

    # 예약 일정에 참가자 추가하기
    result["participants"] = save_info_service.add_participants(
        conn, reservation["id"], participant
    )
    
    # 참가자 추가 후, 예약 일정 다시 가져오기
    refreshed = conn.execute(
        "SELECT * FROM reservations WHERE id = ?",
        (reservation["id"],),
    ).fetchone()
    reservation = reservation_row_to_dict(refreshed)
    result["reservation"] = reservation

    # Google Calendar 동기화
    calendar_result = google_calendar.create_event(
        title=reservation["title"],
        start_time=reservation["start_time"],
        end_time=reservation["end_time"],
        description=reservation.get("description"),
    )

    # Google Calendar 동기화 성공 시, event_id를 reservations 테이블에 저장
    if calendar_result["success"]:
        save_info_service.set_calendar_event_id(
            conn, reservation["id"], calendar_result["event_id"]
        )
        reservation["google_calendar_event_id"] = calendar_result["event_id"]
        result["calendar_sync"] = "success"
    
    # Google Calendar 동기화 실패 시, error 내용 반환
    elif calendar_result["error"] == "calendar_not_configured":
        result["calendar_sync"] = "not_configured"
        
    else:
        result["calendar_sync"] = "failed"
        result["calendar_error"] = calendar_result["error"]

    return result
