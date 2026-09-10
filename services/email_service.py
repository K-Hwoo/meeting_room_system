import datetime
import smtplib
from collections import defaultdict

from datetime import datetime, timedelta
from email.message import EmailMessage
from utils.database import get_connection
from services.find_service import (
    get_reservation_participant_emails,
    find_employee_by_name_or_email,
    list_reservations_with_employee
)

from services.crud_service import list_reservations
 

# SMTP_HOST = os.environ.get("SMTP_HOST")
# SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
# SMTP_USER = os.environ.get("SMTP_USER")
# SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
# FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER)
SMTP_HOST = "smtp.ethereal.email"
SMTP_PORT = 587
SMTP_USER = "rosemarie.orn72@ethereal.email"
SMTP_PASSWORD = "kc9a8M1ySS8P1bbQFQ"
FROM_EMAIL = SMTP_USER

"""
指定されたメールアドレスにメールを送信する。
"""
def send_email(
    recipients: list[str],
    subject: str,
    body: str,
    html_body: str = None,
) -> dict:

    if not recipients:
        return {
            "success": False,
            "error": "recipients_required",
        }

    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        return {
            "success": False,
            "error": "email_not_configured",
        }

    message = EmailMessage()

    message["From"] = FROM_EMAIL
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject

    # 일반 텍스트 fallback
    message.set_content(body)

    # HTML 메일
    if html_body:
        message.add_alternative(
            html_body,
            subtype="html",
        )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(
                SMTP_USER,
                SMTP_PASSWORD,
            )
            server.send_message(message)

        return {
            "success": True,
            "recipients": recipients,
        }

    except Exception as e:
        return {
            "success": False,
            "error": "email_send_failed",
            "detail": str(e),
        }
    

"""
15분 후 시작하는 예약을 찾아 참가자들에게 리마인드 메일을 보낸다.
"""
def send_upcoming_reminders(db_path: str) -> dict:
    conn = get_connection(db_path)

    try:
        now = datetime.now().replace(
            second=0,
            microsecond=0,
        )

        target_start = now + timedelta(minutes=15)
        target_end = target_start + timedelta(minutes=1)

        rows = conn.execute(
            """
            SELECT *
            FROM reservations
            WHERE start_time >= ?
              AND start_time < ?
              AND reminder_sent_at IS NULL
            ORDER BY start_time, id
            """,
            (
                target_start.strftime("%Y-%m-%d %H:%M:%S"),
                target_end.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        ).fetchall()

        sent = []
        failed = []

        for reservation in rows:
            email_result = get_reservation_participant_emails(
                conn,
                reservation["id"],
            )

            if not email_result["success"]:
                failed.append({
                    "reservation_id": reservation["id"],
                    "error": email_result.get("error"),
                })
                continue

            emails = email_result["emails"]

            if not emails:
                failed.append({
                    "reservation_id": reservation["id"],
                    "error": "no_recipient_emails",
                })
                continue

            mail_result = send_email(
                recipients=emails,
                subject=f"会議リマインダー: {reservation['title']}",
                body=(
                    f"15分後に会議が開始します。\n\n"
                    f"タイトル: {reservation['title']}\n"
                    f"開始時間: {reservation['start_time']}\n"
                    f"終了時間: {reservation['end_time']}"
                ),
            )

            if not mail_result["success"]:
                failed.append({
                    "reservation_id": reservation["id"],
                    "error": mail_result.get("error"),
                })
                continue

            conn.execute(
                """
                UPDATE reservations
                SET reminder_sent_at = ?
                WHERE id = ?
                """,
                (
                    now.strftime("%Y-%m-%d %H:%M:%S"),
                    reservation["id"],
                ),
            )

            conn.commit()

            sent.append(reservation["id"])

        return {
            "success": True,
            "sent": sent,
            "failed": failed,
        }

    finally:
        conn.close()
        
    
def send_room_schedule_email(
    conn,
    recipient: str,
    date: str = None,
    start_date: str = None,
    end_date: str = None,
) -> dict:

    # 수신자 검색
    employee_result = find_employee_by_name_or_email(
        conn,
        recipient,
    )

    if not employee_result["success"]:
        return employee_result

    employee = employee_result["employee"]

    # 전체 회의실 예약 조회
    result = list_reservations(
        conn,
        date=date,
        start_date=start_date,
        end_date=end_date,
    )

    if not result["success"]:
        return result

    reservations = result["reservations"]

    schedules_by_date = defaultdict(list)

    for reservation in reservations:
        start = datetime.strptime(
            reservation["start_time"],
            "%Y-%m-%d %H:%M:%S",
        )

        end = datetime.strptime(
            reservation["end_time"],
            "%Y-%m-%d %H:%M:%S",
        )

        date_key = start.strftime("%Y-%m-%d")

        schedules_by_date[date_key].append({
            "start": start.strftime("%H:%M"),
            "end": end.strftime("%H:%M"),
            "title": reservation["title"],
        })

    dates = sorted(schedules_by_date.keys())

    # 예약 없는 날짜 1일 조회도 표시
    if date and not dates:
        dates = [date]

    weekday_labels = [
        "月", "火", "水", "木", "金", "土", "日"
    ]

    # HTML table
    header_cells = ""

    for d in dates:
        dt = datetime.strptime(d, "%Y-%m-%d")

        header_cells += (
            "<th style='padding:10px; "
            "border:1px solid #ccc;'>"
            f"{dt.strftime('%m/%d')} "
            f"{weekday_labels[dt.weekday()]}"
            "</th>"
        )

    schedule_cells = ""

    for d in dates:
        meetings = schedules_by_date.get(d, [])

        content = ""

        if meetings:
            for meeting in meetings:
                content += (
                    "<div style='"
                    "padding:8px; "
                    "margin-bottom:6px; "
                    "border:1px solid #ddd; "
                    "border-radius:6px;"
                    "'>"
                    f"<strong>{meeting['start']}–{meeting['end']}</strong>"
                    "<br>"
                    f"{meeting['title']}"
                    "</div>"
                )
        else:
            content = "-"

        schedule_cells += (
            "<td style='"
            "padding:10px; "
            "vertical-align:top; "
            "border:1px solid #ccc;"
            "'>"
            f"{content}"
            "</td>"
        )

    html_body = f"""
    <html>
    <body>
        <p>{employee['name']} 様</p>

        <p>会議室の利用予定をお知らせします。</p>

        <table style="
            border-collapse:collapse;
            width:100%;
        ">
            <tr>
                {header_cells}
            </tr>

            <tr>
                {schedule_cells}
            </tr>
        </table>

        <p>
            予約件数：{len(reservations)}件
        </p>
    </body>
    </html>
    """

    text_body = (
        f"{employee['name']} 様\n\n"
        f"会議室利用予定：{len(reservations)}件"
    )

    return send_email(
        recipients=[employee["email"]],
        subject="【会議室利用予定】",
        body=text_body,
        html_body=html_body,
    )
    
    
def send_employee_schedule_email(
    conn,
    employee: str,
    date: str = None,
    start_date: str = None,
    end_date: str = None,
) -> dict:

    employee_result = find_employee_by_name_or_email(
        conn,
        employee,
    )

    if not employee_result["success"]:
        return employee_result

    employee_data = employee_result["employee"]

    result = list_reservations_with_employee(
        conn,
        email=employee_data["email"],
        date=date,
        start_date=start_date,
        end_date=end_date,
    )

    if not result["success"]:
        return result

    reservations = result["reservations"]

    rows = ""

    for reservation in reservations:

        start = datetime.strptime(
            reservation["start_time"],
            "%Y-%m-%d %H:%M:%S",
        )

        end = datetime.strptime(
            reservation["end_time"],
            "%Y-%m-%d %H:%M:%S",
        )

        rows += f"""
        <tr>
            <td style="padding:8px; border:1px solid #ccc;">
                {start.strftime("%Y-%m-%d")}
            </td>

            <td style="padding:8px; border:1px solid #ccc;">
                {start.strftime("%H:%M")}–{end.strftime("%H:%M")}
            </td>

            <td style="padding:8px; border:1px solid #ccc;">
                {reservation["title"]}
            </td>
        </tr>
        """

    if not rows:
        rows = """
        <tr>
            <td colspan="3"
                style="padding:12px; border:1px solid #ccc;">
                該当する予定はありません。
            </td>
        </tr>
        """

    html_body = f"""
    <html>
    <body>

        <p>{employee_data['name']} 様</p>

        <p>会議予定をお知らせします。</p>

        <table style="
            border-collapse:collapse;
            width:100%;
        ">

            <tr>
                <th style="padding:8px; border:1px solid #ccc;">
                    日付
                </th>

                <th style="padding:8px; border:1px solid #ccc;">
                    時間
                </th>

                <th style="padding:8px; border:1px solid #ccc;">
                    会議名
                </th>
            </tr>

            {rows}

        </table>

    </body>
    </html>
    """

    return send_email(
        recipients=[employee_data["email"]],
        subject=f"【会議予定】{employee_data['name']} 様",
        body=f"{employee_data['name']} 様の会議予定です。",
        html_body=html_body,
    )