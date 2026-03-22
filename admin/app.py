import os
import uvicorn
from pathlib import Path

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer, BadSignature
from loguru import logger

from config import settings
from database.crud import (
    get_all_users,
    get_user,
    get_stats,
    ban_user,
    set_user_plan,
    add_tokens,
    get_all_payments,
    get_payment_stats,
    get_payment_by_external_id,
    update_payment_status,
)
from config import PLANS

BASE_DIR = Path(__file__).parent

app = FastAPI(title="AI Bot Admin Panel", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_serializer = URLSafeSerializer(settings.ADMIN_SECRET_KEY, salt="admin-session")
SESSION_COOKIE = "admin_session"


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _create_session_token() -> str:
    return _serializer.dumps({"authenticated": True})


def _verify_session(token: str | None) -> bool:
    if not token:
        return False
    try:
        data = _serializer.loads(token)
        return data.get("authenticated") is True
    except BadSignature:
        return False


def get_current_admin(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not _verify_session(token):
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return True


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/admin/login")
async def login_submit(request: Request, password: str = Form(...)):
    if password == settings.ADMIN_SECRET_KEY:
        token = _create_session_token()
        response = RedirectResponse(url="/admin/dashboard", status_code=303)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            samesite="lax",
            # Set secure=True in production when serving over HTTPS
            secure=False,
        )
        logger.info("Admin logged in")
        return response
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Неверный пароль"}, status_code=401
    )


@app.get("/admin/logout")
async def logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, _: bool = Depends(get_current_admin)):
    stats = await get_stats()
    users, _ = await get_all_users(page=1, per_page=10)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats, "recent_users": users},
    )


# ---------------------------------------------------------------------------
# Users list
# ---------------------------------------------------------------------------

@app.get("/admin/users", response_class=HTMLResponse)
async def users_list(
    request: Request,
    page: int = 1,
    search: str = "",
    _: bool = Depends(get_current_admin),
):
    per_page = 20
    users, total = await get_all_users(page=page, per_page=per_page, search=search or None)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "users": users,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "search": search,
        },
    )


# ---------------------------------------------------------------------------
# User detail
# ---------------------------------------------------------------------------

@app.get("/admin/users/{user_id}", response_class=HTMLResponse)
async def user_detail(
    request: Request,
    user_id: int,
    _: bool = Depends(get_current_admin),
):
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return templates.TemplateResponse(
        "user_detail.html",
        {"request": request, "user": user, "plans": list(PLANS.keys())},
    )


@app.post("/admin/users/{user_id}/ban")
async def toggle_ban(user_id: int, _: bool = Depends(get_current_admin)):
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404)
    await ban_user(user_id, not user.is_banned)
    logger.info(f"Admin toggled ban for user {user_id} -> {not user.is_banned}")
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@app.post("/admin/users/{user_id}/set_plan")
async def change_plan(
    user_id: int,
    plan: str = Form(...),
    _: bool = Depends(get_current_admin),
):
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail="Неверный тариф")
    await set_user_plan(user_id, plan)
    logger.info(f"Admin set plan {plan} for user {user_id}")
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


@app.post("/admin/users/{user_id}/add_tokens")
async def change_tokens(
    user_id: int,
    amount: int = Form(...),
    _: bool = Depends(get_current_admin),
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть > 0")
    await add_tokens(user_id, amount)
    logger.info(f"Admin added {amount} tokens to user {user_id}")
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


# ---------------------------------------------------------------------------
# Stripe webhook (automatic payment confirmation)
# ---------------------------------------------------------------------------

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    from payments.stripe_pay import verify_stripe_webhook
    event = verify_stripe_webhook(payload, sig_header)
    if event is None:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session.get("id")
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        plan = metadata.get("plan")

        if session_id and user_id and plan:
            if plan not in PLANS:
                logger.warning(f"Stripe webhook: unknown plan '{plan}' for user {user_id}")
            else:
                payment = await get_payment_by_external_id(session_id)
                if payment and payment.status != "succeeded":
                    await update_payment_status(payment.id, "succeeded")
                    await set_user_plan(int(user_id), plan)
                    logger.info(
                        f"Stripe webhook: user {user_id} upgraded to {plan} (session {session_id})"
                    )

    return Response(status_code=200)


# ---------------------------------------------------------------------------
# YooKassa webhook (automatic payment confirmation)
# ---------------------------------------------------------------------------

@app.post("/webhooks/yookassa")
async def yookassa_webhook(request: Request):
    payload = await request.body()
    # YooKassa sends the IP; signature check uses secret key as HMAC key
    signature = request.headers.get("Signature", "")

    from payments.yookassa_pay import verify_yookassa_webhook
    event = verify_yookassa_webhook(payload, signature)
    if event is None:
        # Log the failed verification for security monitoring
        logger.warning(
            f"YooKassa webhook verification failed from {request.client.host}"
        )
        # Accept the request (YooKassa retries otherwise) but do nothing
        return Response(status_code=200)

    event_type = event.get("event", "")
    if event_type == "payment.succeeded":
        payment_obj = event.get("object", {})
        payment_id = payment_obj.get("id")
        metadata = payment_obj.get("metadata", {})
        user_id = metadata.get("user_id")
        plan = metadata.get("plan")

        if payment_id and user_id and plan:
            if plan not in PLANS:
                logger.warning(f"YooKassa webhook: unknown plan '{plan}' for user {user_id}")
            else:
                payment = await get_payment_by_external_id(payment_id)
                if payment and payment.status != "succeeded":
                    await update_payment_status(payment.id, "succeeded")
                    await set_user_plan(int(user_id), plan)
                    logger.info(
                        f"YooKassa webhook: user {user_id} upgraded to {plan} (payment {payment_id})"
                    )

    return Response(status_code=200)


# ---------------------------------------------------------------------------
# Payments list
# ---------------------------------------------------------------------------

@app.get("/admin/payments", response_class=HTMLResponse)
async def payments_list(
    request: Request,
    page: int = 1,
    _: bool = Depends(get_current_admin),
):
    per_page = 20
    payments, total = await get_all_payments(page=page, per_page=per_page)
    total_pages = max(1, (total + per_page - 1) // per_page)
    pay_stats = await get_payment_stats()
    return templates.TemplateResponse(
        "payments.html",
        {
            "request": request,
            "payments": payments,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "pay_stats": pay_stats,
        },
    )


# ---------------------------------------------------------------------------
# API stats (for charts / JS)
# ---------------------------------------------------------------------------

@app.get("/admin/api/stats")
async def api_stats(_: bool = Depends(get_current_admin)):
    stats = await get_stats()
    return JSONResponse(stats)


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return RedirectResponse(url="/admin/login")


# ---------------------------------------------------------------------------
# Exception handler for 302 redirect (raised by get_current_admin)
# ---------------------------------------------------------------------------

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 302:
        return RedirectResponse(url=exc.headers["Location"])
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE_DIR.parent))
    uvicorn.run(
        "admin.app:app",
        host="0.0.0.0",
        port=settings.ADMIN_PORT,
        reload=False,
    )
