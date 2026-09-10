from utils.format_tools import parse_text_to_list

"""
이메일에 해당하는 사원이 참여하는 예약 목록을 반환한다.
"""
def list_reservations_with_employee(
    conn,
    email: str,
    date: str = None,
    start_date: str = None,
    end_date: str = None,
) -> dict:

    employee = conn.execute(
        """
        SELECT id
        FROM employees
        WHERE LOWER(email) = LOWER(?)
        """,
        (email.strip(),),
    ).fetchone()

    if employee is None:
        return {
            "success": False,
            "error": "EMPLOYEE_NOT_FOUND",
        }

    employee_id = employee["id"]

    query = """
        SELECT
            id,
            title,
            start_time,
            end_time,
            participants
        FROM reservations
        WHERE 1=1
    """

    params = []

    if date:
        query += " AND date(start_time) = date(?)"
        params.append(date)

    elif start_date or end_date:

        range_start = start_date or end_date
        range_end = end_date or start_date

        query += """
            AND date(start_time) <= date(?)
            AND date(end_time) >= date(?)
        """

        params.extend([
            range_end,
            range_start,
        ])

    query += " ORDER BY start_time, id"

    rows = conn.execute(
        query,
        params,
    ).fetchall()

    reservations = []

    for r in rows:
        if employee_id in parse_text_to_list(
            r["participants"]
        ):
            reservations.append({
                "id": r["id"],
                "title": r["title"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
            })

    return {
        "success": True,
        "reservations": reservations,
    }


"""
예약 참가자의 사원 정보를 반환한다.
- reservations.participants의 사원 ID 배열을 이름/이메일 정보로 확장한다.
"""
def get_reservation_participants(conn, reservation_id: int) -> dict:
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

    participant_ids = parse_text_to_list(row["participants"])
    
    if not participant_ids:
        return {
            "success": True, 
            "participants": []
        }

    placeholders = ",".join("?" for _ in participant_ids)
    
    employees = conn.execute(
        f"""
        SELECT id, name, email
        FROM employees
        WHERE id IN ({placeholders})
        """,
        participant_ids,
    ).fetchall()
    
    employees_by_id = {
        employee["id"]: {
            "id": employee["id"],
            "name": employee["name"],
            "email": employee["email"],
        }
        for employee in employees
    }
    
    return {
        "success": True,
        "participants": [
            employees_by_id[participant_id] for participant_id in participant_ids
            if participant_id in employees_by_id
        ],
    }


"""
예약 참가자들의 이메일 주소 목록을 반환한다.
"""
def get_reservation_participant_emails(conn, reservation_id: int,) -> dict:
    result = get_reservation_participants(
        conn,
        reservation_id,
    )

    if not result["success"]:
        return result

    emails = [
        participant["email"]
        for participant in result["participants"]
        if participant.get("email")
    ]

    return {
        "success": True,
        "reservation_id": reservation_id,
        "emails": emails,
    }
    
    
def find_employee_by_name_or_email(
    conn,
    value: str,
) -> dict:

    value = value.strip()

    employee = conn.execute(
        """
        SELECT id, name, email
        FROM employees
        WHERE LOWER(email) = LOWER(?)
           OR name = ?
        """,
        (value, value),
    ).fetchone()

    if employee is None:
        return {
            "success": False,
            "error": "employee_not_found",
            "given": value,
        }

    return {
        "success": True,
        "employee": {
            "id": employee["id"],
            "name": employee["name"],
            "email": employee["email"],
        },
    }