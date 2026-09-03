# 사원 인증 / 社員認証
def authenticate_employee(conn, email: str) -> dict : 
    """
    Returns:
        成功: {"authenticated": true,
                "employee": {"id":N, "name":.., "email": <入力値>, "is_admin":bool}}
                
        失敗: {"authenticated": false,
                "employee": {"id": None, "name": ..., "email": <入力値>, "is_admin": false}}
    """
    
    cursor = conn.execute(
        "SELECT id, name, email, is_admin FROM employees WHERE email = ?",
        (email,),
    )
    employee = cursor.fetchone()

    if employee is None:
        return {
            "authenticated": False,
            "employee": {
                "id": None, 
                "name": "Error: EMPLOYEE_NOT_FOUND", 
                "email": email,
                "is_admin": False
            },
        }

    return {
        "authenticated": True,
        "employee": {
            "id": employee["id"],
            "name": employee["name"],
            "email": employee["email"],
            "is_admin": bool(employee["is_admin"]),
        },
    }