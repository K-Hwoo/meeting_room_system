import json
from datetime import datetime, timedelta

from utils.server_setting import VALID_CATEGORIES
from utils.format_tools import parse_date_only, parse_hhmm
from services.crud_service import create_reservation_integrated
from utils.database import get_connection

def create_recurring_reservation(
    conn,
    title: str, start_date: str, weekday: int,
    start_time: str, end_time: str, category: str,
    participant_names: list, description: str = None,
) -> dict:

    if not title:
        return {
            "success": False,
            "error": "title_required",
        }
        
    normalized_date = parse_date_only(start_date)
    if normalized_date is None:
        return {
            "success": False,
            "error": "invalid_start_date",
            "given": start_date,
        }

    if not isinstance(weekday, int) or weekday not in range(7):
        return {
            "success": False,
            "error": "invalid_weekday",
            "expected": "0-6",
            "given": weekday,
        }
        
    start_minutes = parse_hhmm(start_time)
    end_minutes = parse_hhmm(end_time)
    if start_minutes is None or end_minutes is None:
        return {
            "success": False,
            "error": "invalid_time_format",
            "expected": "HH:MM",
        }

    # LLM이 체크해주니까 필요 없어보이지만, 혹시 모르니 남겨둠
    if start_minutes >= end_minutes:
        return {
            "success": False,
            "error": "end_before_start",
        }
        
    if category not in VALID_CATEGORIES:
        return {
            "success": False,
            "error": "invalid_category",
            "valid_categories": VALID_CATEGORIES,
            "given": category,
        }

    if not participant_names:
        return {
            "success": False,
            "error": "participants_required",
        }

    participant_names_json = json.dumps(
        participant_names,
        ensure_ascii=False,
    )

    cur = conn.execute(
        """
        INSERT INTO recurring_reservations
            (
                title, start_date, weekday,
                start_time, end_time, category,
                participant_names, description
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title, normalized_date, weekday,
            start_time, end_time, category,
            participant_names_json, description
        ),
    )

    conn.commit()

    recurring_id = cur.lastrowid

    row = conn.execute(
        "SELECT * FROM recurring_reservations WHERE id = ?",
        (recurring_id,),
    ).fetchone()

    return {
        "success": True,
        "recurring_reservation": dict(row),
    }
    
    
def generate_weekly_dates(
    start_date: str,
    weekday: int,
    generated_until: str = None,
    days_ahead: int = 30,
) -> list[str]:

    rule_start = datetime.strptime(
        start_date,
        "%Y-%m-%d",
    ).date()

    today = datetime.now().date()

    # 최초 생성
    if generated_until is None:
        current = max(rule_start, today)

        # start_date 이후의 첫 해당 요일 찾기
        while current.weekday() != weekday:
            current += timedelta(days=1)

    # 이미 이전에 생성한 적이 있으면
    else:
        last_generated = datetime.strptime(
            generated_until,
            "%Y-%m-%d",
        ).date()

        current = last_generated + timedelta(days=1)

        # 다음 해당 요일까지 이동
        while current.weekday() != weekday:
            current += timedelta(days=1)

    limit = today + timedelta(days=days_ahead)

    dates = []

    while current <= limit:
        dates.append(
            current.strftime("%Y-%m-%d")
        )

        # 이후에는 매주 같은 요일
        current += timedelta(days=7)

    return dates


def generate_recurring_instances(
    conn,
    recurring_id: int,
) -> dict:

    row = conn.execute(
        """
        SELECT *
        FROM recurring_reservations
        WHERE id = ?
        """,
        (recurring_id,),
    ).fetchone()

    if row is None:
        return {
            "success": False,
            "error": "recurring_reservation_not_found",
            "recurring_id": recurring_id,
        }

    recurring = dict(row)

    participant_names = json.loads(
        recurring["participant_names"]
    )

    dates = generate_weekly_dates(
        start_date=recurring["start_date"],
        weekday=recurring["weekday"],
        generated_until=recurring["generated_until"],
        days_ahead=30,
    )

    created = []
    conflicts = []

    for date in dates:

        start_datetime = (
            f"{date} {recurring['start_time']}"
        )

        end_datetime = (
            f"{date} {recurring['end_time']}"
        )

        result = create_reservation_integrated(
            conn=conn,
            title=recurring["title"],
            start_time=start_datetime,
            end_time=end_datetime,
            category=recurring["category"],
            participant=participant_names,
            description=recurring["description"],
        )

        if result["success"]:
            reservation_id = result["reservation"]["id"]

            # 이 예약이 어떤 정기예약에서 생성됐는지 연결
            conn.execute(
                """
                UPDATE reservations
                SET recurring_reservation_id = ?
                WHERE id = ?
                """,
                (
                    recurring_id,
                    reservation_id,
                ),
            )

            conn.commit()

            created.append({
                "date": date,
                "reservation_id": reservation_id,
            })

            continue

        # 기존 예약과 충돌한 경우
        if result.get("error") == "time_overlap":

            conflicts.append({
                "date": date,
                "conflicts": result.get(
                    "conflicts",
                    [],
                ),
            })

            continue

        return {
            "success": False,
            "error": "recurring_instance_creation_failed",
            "date": date,
            "reason": result,
        }

    # 어디까지 생성 시도했는지 기록
    if dates:
        conn.execute(
            """
            UPDATE recurring_reservations
            SET generated_until = ?
            WHERE id = ?
            """,
            (
                dates[-1],
                recurring_id,
            ),
        )

        conn.commit()

    return {
        "success": True,
        "recurring_id": recurring_id,
        "created": created,
        "conflicts": conflicts,
    }
    
    
def list_recurring_reservations(
    conn,
) -> dict:

    rows = conn.execute(
        """
        SELECT *
        FROM recurring_reservations
        ORDER BY start_date, start_time, id
        """
    ).fetchall()

    return {
        "success": True,
        "recurring_reservations": [
            dict(row)
            for row in rows
        ],
    }
    
    
def delete_recurring_reservation(
    conn,
    recurring_id: int,
) -> dict:

    row = conn.execute(
        """
        SELECT *
        FROM recurring_reservations
        WHERE id = ?
        """,
        (recurring_id,),
    ).fetchone()

    if row is None:
        return {
            "success": False,
            "error": "recurring_reservation_not_found",
            "recurring_id": recurring_id,
        }

    recurring = dict(row)

    conn.execute(
        """
        DELETE FROM recurring_reservations
        WHERE id = ?
        """,
        (recurring_id,),
    )

    conn.commit()

    return {
        "success": True,
        "deleted_recurring_reservation": recurring,
    }
    
def generate_all_recurring_reservations(
    conn,
) -> dict:

    rows = conn.execute(
        """
        SELECT id
        FROM recurring_reservations
        ORDER BY id
        """
    ).fetchall()

    results = []

    for row in rows:
        result = generate_recurring_instances(
            conn,
            row["id"],
        )

        results.append({
            "recurring_id": row["id"],
            "result": result,
        })

    return {
        "success": True,
        "processed_count": len(rows),
        "results": results,
    }


def run_recurring_reservation_scheduler(
    db_path: str,
) -> dict:

    conn = get_connection(db_path)

    try:
        return generate_all_recurring_reservations(
            conn
        )

    finally:
        conn.close()