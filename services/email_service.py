import datetime
import smtplib

from datetime import datetime, timedelta
from email.message import EmailMessage
from utils.database import get_connection
from services.find_service import get_reservation_participant_emails

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
    message.set_content(body)

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