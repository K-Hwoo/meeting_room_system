from utils.format_tools import row_to_dict, validate_reservation_input
from services.crud_service import find_overlapping, create_reservation_integrated

import json


def create_reservation_request(
    conn,
    title: str, start_time: str, end_time: str,
    category: str, participant_names: list, description: str = None,
) -> dict:
    """
    一般社員が予約をリクエストする。

    Returns:
        成功: {"success": true, "request": {...}}
             
        失敗: {"success": false, "error": "time_overlap", "conflicts": [...]}
    """
    if not participant_names:
        return {
            "success": False,
            "error": "missing_fields",
            "missing_fields": ["participant_names"],
        }

    validation = validate_reservation_input(
        title,
        start_time,
        end_time,
        category,
    )

    if not validation["success"]:
        return validation

    norm_start = validation["start_time"]
    norm_end = validation["end_time"]

    conflicts = find_overlapping(conn, norm_start, norm_end)

    if conflicts:
        return {
            "success": False,
            "error": "conflict_found",
            "conflicts": [row_to_dict(c) for c in conflicts]
        }


    participant_names_json = json.dumps(
        participant_names, 
        ensure_ascii=False,
    )

    cur = conn.execute(
        """
        INSERT INTO reservation_requests
            (
                title, start_time, end_time, 
                category, description, participant_names, status
            )
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
        (
            title, norm_start, norm_end, 
            category, description, participant_names_json
        ),
    )
    
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute(
        "SELECT * FROM reservation_requests WHERE id = ?", 
        (new_id,)
    ).fetchone()

    return {
        "success": True,
        "request": row_to_dict(row),
    }


def list_reservation_requests(conn, status: str = None) -> dict:
    """
    予約リクエスト一覧を取得する。
    status: "pending" | "approved" | "rejected"。省略すると全件。
    """
    valid_statuses = ["pending", "approved", "rejected"]
    if status is not None and status not in valid_statuses:
        return {
            "success": False,
            "error": "invalid_status",
            "valid_statuses": valid_statuses,
            "given": status,
        }

    if status is not None:
        rows = conn.execute(
            "SELECT * FROM reservation_requests WHERE status = ? ORDER BY created_at",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM reservation_requests ORDER BY created_at"
        ).fetchall()

    return {"success": True, "requests": [row_to_dict(r) for r in rows]}


def approve_reservation_request(conn, request_id: int) -> dict:
    """
    保留中のリクエストを承認し、実際の予約を作成する。
    承認時点で改めて重複チェックを行い、他の予約と衝突していれば失敗する
    (リクエスト自体は pending のまま残るので、後で再判断できる)。

    実際の予約作成、参加者の紐付け、Google Calendar同期は
    reservation_service に委譲する。
    """
    row = conn.execute("SELECT * FROM reservation_requests WHERE id = ?", (request_id,)).fetchone()
    if row is None:
        return {
            "success": False, 
            "error": "request_not_found", 
            "request_id": request_id
        }

    req = row_to_dict(row)
    
    if req["status"] != "pending":
        return {
            "success": False, 
            "error": "already_processed", 
            "current_status": req["status"]
        }

    participant_names = []
    if req.get("participant_names"):
        try:
            participant_names = json.loads(req["participant_names"])
        except (TypeError, ValueError):
            participant_names = []

    result = create_reservation_integrated(
        conn=conn,
        title=req["title"],
        start_time=req["start_time"],
        end_time=req["end_time"],
        category=req["category"],
        participant=participant_names,
        description=req["description"],
    )
    
    if not result["success"]:
        # 承認時点で重複等が発生した場合、リクエストは pending のまま維持
        return {
            "success": False, 
            "error": "approve_failed", 
            "reason": result
        }

    new_reservation_id = result["reservation"]["id"]

    conn.execute(
        """
        UPDATE reservation_requests
        SET status = 'approved', reservation_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (new_reservation_id, request_id),
    )
    conn.commit()
    
    updated_row = conn.execute("SELECT * FROM reservation_requests WHERE id = ?", (request_id,)).fetchone()

    response = {
        "success": True, 
        "request": row_to_dict(updated_row),
        "reservation": result["reservation"]
    }
    
    if "participants" in result:
        response["participants"] = result["participants"]
        
    if "calendar_sync" in result:
        response["calendar_sync"] = result["calendar_sync"]
        
    if "calendar_error" in result:
        response["calendar_error"] = result["calendar_error"]
        
    return response


def reject_reservation_request(conn, request_id: int, reason: str) -> dict:
    """保留中のリクエストを却下する。実際の予約は作成しない。"""
    if not isinstance(reason, str) or not reason.strip():
        return {
            "success": False,
            "error": "reject_reason_required",
            "message": "却下理由を入力してください。",
        }
    reason = reason.strip()

    row = conn.execute("SELECT * FROM reservation_requests WHERE id = ?", (request_id,)).fetchone()
    if row is None:
        return {
            "success": False, 
            "error": "request_not_found", 
            "request_id": request_id
        }

    req = row_to_dict(row)
    if req["status"] != "pending":
        return {
            "success": False, 
            "error": "already_processed", 
            "current_status": req["status"]
        }

    conn.execute(
        """
        UPDATE reservation_requests
        SET status = 'rejected', reject_reason = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (reason, request_id),
    )
    conn.commit()
    updated_row = conn.execute("SELECT * FROM reservation_requests WHERE id = ?", (request_id,)).fetchone()

    return {"success": True, "request": row_to_dict(updated_row)}
