from flask import request

SESSION_TOKENS = {}


def get_session_token():
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1].strip()

    return request.headers.get("X-Session-Token") or request.args.get("session_token") or ""


def get_authenticated_user_id():
    token = get_session_token()
    if token and token in SESSION_TOKENS:
        return SESSION_TOKENS[token]
    return None
