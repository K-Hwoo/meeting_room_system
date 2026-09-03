import json

# 회의실 예약 정보에 구글캘린더 일정 id 추가
# 予約にGoogleカレンダーのイベントIDを紐付けて保存する。
def set_calendar_event_id(conn, reservation_id: int, event_id: str) -> dict:
    conn.execute(
        "UPDATE reservations SET google_calendar_event_id = ? WHERE id = ?",
        (event_id, reservation_id),
    )
    conn.commit()
    
    return {
        "success": True,
        "reservation_id": reservation_id, 
        "event_id": event_id
    }


# 예약 행의 participants 컬럼(JSON 배열)에 참여 사원 ID를 저장
def add_participants(conn, reservation_id: int, names: list) -> dict:
    row = conn.execute(
        "SELECT participants FROM reservations WHERE id = ?",
        (reservation_id,),
    ).fetchone()
    
    if row is None:
        return {
            "success": False, 
            "error": "reservation_not_found", 
            "reservation_id": reservation_id
        }

    try:
        current_ids = json.loads(row["participants"] or "[]")
        
    except (TypeError, ValueError):
        current_ids = []

    if not isinstance(current_ids, list):
        current_ids = []

    added = []
    not_found = []

    for name in names or []:
        employee = conn.execute(
            "SELECT id, name, email FROM employees WHERE name = ?",
            (name,),
        ).fetchone()

        if employee is None:
            not_found.append(name)
            continue

        employee_id = employee["id"]
        if employee_id not in current_ids:
            current_ids.append(employee_id)

        added.append({
            "id": employee_id,
            "name": employee["name"],
            "email": employee["email"],
        })

    conn.execute(
        "UPDATE reservations SET participants = ? WHERE id = ?",
        (json.dumps(current_ids, ensure_ascii=False), reservation_id),
    )
    conn.commit()

    return {
        "success": True,
        "added": added,
        "not_found": not_found,
    }
