"""Telegram: the 08:00 morning report to the director (and anyone else the admin adds)."""
import hashlib
import os
import time

import amo  # kv helpers

API = "https://api.telegram.org/bot{token}/{method}"


def token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def configured() -> bool:
    return bool(token())


async def call(http, method: str, **params) -> dict:
    try:
        r = await http.post(API.format(token=token(), method=method), json=params, timeout=20)
        return r.json()
    except Exception as e:  # network trouble: report it, never crash the caller
        return {"ok": False, "description": str(e)}


def recipients(con) -> list:
    return amo.kv_get(con, "tg_chats", []) or []


def save_recipients(con, chats: list):
    amo.kv_set(con, "tg_chats", chats)


async def bot_name(http) -> str:
    r = await call(http, "getMe")
    return (r.get("result") or {}).get("username", "") if r.get("ok") else ""


def secret() -> str:
    """Shared secret Telegram sends back with every webhook call."""
    return hashlib.sha256((token() + os.getenv("CRON_SECRET", "")).encode()).hexdigest()[:40]


def remember_start(con, chat: dict):
    """Someone pressed Start: keep them as a candidate the admin can add on the Telegram page."""
    if chat.get("type") != "private" or not chat.get("id"):
        return
    seen = amo.kv_get(con, "tg_seen", []) or []
    name = " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x) or chat.get("username") or str(chat["id"])
    seen = [c for c in seen if c["id"] != chat["id"]] + [{"id": chat["id"], "name": name, "username": chat.get("username") or "",
                                                         "ts": int(time.time())}]
    amo.kv_set(con, "tg_seen", seen[-30:])


async def ensure_webhook(http, url: str) -> str:
    info = await call(http, "getWebhookInfo")
    if (info.get("result") or {}).get("url") == url:
        return "ok"
    r = await call(http, "setWebhook", url=url, secret_token=secret(), allowed_updates=["message", "callback_query"],
                   drop_pending_updates=False)
    return "set" if r.get("ok") else r.get("description", "error")


async def candidates(http, con=None) -> list:
    """People who pressed Start: from the webhook (kept in the database), else from getUpdates."""
    out = {}
    if con is not None:
        for c in amo.kv_get(con, "tg_seen", []) or []:
            out[c["id"]] = {"id": c["id"], "name": c["name"], "username": c.get("username", "")}
    r = await call(http, "getUpdates", limit=100)
    for u in r.get("result") or []:
        chat = (u.get("message") or u.get("my_chat_member") or {}).get("chat") or {}
        if chat.get("type") == "private" and chat.get("id"):
            name = " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x) or chat.get("username") or str(chat["id"])
            out[chat["id"]] = {"id": chat["id"], "name": name, "username": chat.get("username") or ""}
    return list(out.values())


def keyboard(buttons: list) -> dict:
    """[(label, callback_data), ...] -> one button per row."""
    return {"inline_keyboard": [[{"text": t, "callback_data": d}] for t, d in buttons]}


async def send(http, chat_id, text: str, buttons: list | None = None, markdown: bool = True) -> tuple[bool, str]:
    extra = {"reply_markup": keyboard(buttons)} if buttons else {}
    r = {"ok": False}
    if markdown:
        r = await call(http, "sendMessage", chat_id=chat_id, text=text, parse_mode="Markdown", disable_web_page_preview=True, **extra)
    if not r.get("ok"):  # a name with * or _ breaks Markdown: send it plain
        r = await call(http, "sendMessage", chat_id=chat_id, text=text.replace("*", "") if markdown else text,
                       disable_web_page_preview=True, **extra)
    return bool(r.get("ok")), r.get("description", "")


async def send_file(http, chat_id, filename: str, data: bytes, caption: str = "") -> tuple[bool, str]:
    try:
        r = await http.post(API.format(token=token(), method="sendDocument"), timeout=60,
                            data={"chat_id": str(chat_id), "caption": caption[:1000]}, files={"document": (filename, data)})
        j = r.json()
    except Exception as e:
        return False, str(e)
    return bool(j.get("ok")), j.get("description", "")
