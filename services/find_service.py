from utils.format_tools import parse_json_list


def list_reservations_with_employee(conn, email: str) -> dict:
    """이메일에 해당하는 사원이 참여하는 예약 목록을 반환한다."""
    employee = conn.execute(
        "SELECT id FROM employees WHERE LOWER(email) = LOWER(?)",
        (email.strip(),),
    ).fetchone()

    if employee is None:
        return {
            "success": False,
            "error": "EMPLOYEE_NOT_FOUND",
            "message": "該当する社員が見つかりませんでした。",
        }

    employee_id = employee["id"]
    rows = conn.execute(
        "SELECT id, title, start_time, end_time, participants FROM reservations ORDER BY start_time, id"
    ).fetchall()

    reservations = []
    for r in rows:
        if employee_id in parse_json_list(r["participants"]):
            reservations.append({
                "id": r["id"],
                "title": r["title"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
            })

    if not reservations:
        return {
            "success": False,
            "error": "NO_RESERVATIONS_FOUND",
            "message": "該当する社員の参加予定が見つかりませんでした。",
        }

    return {"success": True, "reservations": reservations}


def get_reservation_participants(conn, reservation_id: int) -> dict:
    """reservations.participants의 사원 ID 배열을 이름/이메일 정보로 확장한다."""
    row = conn.execute(
        "SELECT participants FROM reservations WHERE id = ?",
        (reservation_id,),
    ).fetchone()

    if row is None:
        return {"success": False, "error": "reservation_not_found", "reservation_id": reservation_id}

    participant_ids = parse_json_list(row["participants"])
    if not participant_ids:
        return {"success": True, "participants": []}

    placeholders = ",".join("?" for _ in participant_ids)
    employees = conn.execute(
        f"SELECT id, name, email FROM employees WHERE id IN ({placeholders})",
        participant_ids,
    ).fetchall()
    by_id = {e["id"]: {"id": e["id"], "name": e["name"], "email": e["email"]} for e in employees}

    return {
        "success": True,
        "participants": [by_id[i] for i in participant_ids if i in by_id],
    }
