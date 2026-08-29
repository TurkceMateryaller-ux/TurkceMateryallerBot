from __future__ import annotations

import hashlib
import logging
import os
import threading
import time

import requests
from flask import Flask, abort, request

from ai_service import AIService
from config import load_settings
from database import Database
from keyboards import (
    back_keyboard,
    main_keyboard,
    request_confirmation_keyboard,
    subscription_keyboard,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("turkce_telegram_bot")


class TelegramBot:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.base_url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"
        self.http = requests.Session()
        self.db = Database(self.settings.database_path)
        self.db.initialize()
        self.ai = AIService(self.settings.gemini_api_key, self.settings.gemini_model)
        self.states: dict[int, str] = {}
        self.interviews: dict[int, dict] = {}
        self.offset = 0

    def call(self, method: str, **payload):
        response = self.http.post(f"{self.base_url}/{method}", json=payload, timeout=40)
        if not response.ok:
            raise RuntimeError(
                f"Telegram {method} failed ({response.status_code}): {response.text[:500]}"
            )
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} returned an error: {data}")
        return data.get("result")

    def is_admin(self, user_id: int) -> bool:
        return self.settings.admin_telegram_id == user_id

    def send(self, chat_id: int, text: str, keyboard: dict | None = None) -> None:
        text = str(text)
        chunks = [text[i : i + 4000] for i in range(0, len(text), 4000)] or [""]
        for index, chunk in enumerate(chunks):
            payload = {"chat_id": chat_id, "text": chunk}
            if keyboard is not None and index == len(chunks) - 1:
                payload["reply_markup"] = keyboard
            self.call("sendMessage", **payload)

    def show_menu(self, user_id: int) -> None:
        self.states.pop(user_id, None)
        self.interviews.pop(user_id, None)
        self.send(user_id, "Выберите нужный раздел:", main_keyboard(self.is_admin(user_id)))

    def handle(self, user_id: int, text: str) -> None:
        normalized = text.strip().lower()
        self.db.ensure_user(user_id)
        if normalized in {"/start", "начать", "старт", "меню", "в главное меню"}:
            self.show_menu(user_id)
            return

        state = self.states.get(user_id)
        if state == "request_interview":
            self.continue_interview(user_id, text)
            return
        if state == "request_confirmation":
            self.confirm_request(user_id, normalized)
            return
        if state in {"ai_task", "ai_lesson"}:
            kind = "упражнение с ответами" if state == "ai_task" else "план урока"
            self.send(user_id, "Готовлю результат…")
            try:
                answer = self.ai.generate(text, kind)
            except Exception:
                logger.exception("AI request failed")
                answer = "Не удалось получить ответ ИИ. Попробуйте ещё раз позднее."
            self.states.pop(user_id, None)
            self.send(user_id, answer, main_keyboard(self.is_admin(user_id)))
            return

        handlers = {
            "найти материал": self.materials,
            "заказать материал": self.new_request,
            "создать задание с ии": lambda uid: self.start_ai(uid, "ai_task"),
            "план урока": lambda uid: self.start_ai(uid, "ai_lesson"),
            "мои заявки": self.my_requests,
            "рассылка": self.subscription,
            "подписаться": lambda uid: self.change_subscription(uid, True),
            "отписаться": lambda uid: self.change_subscription(uid, False),
            "связаться с автором": self.contact,
            "администратор": self.admin,
        }
        handler = handlers.get(normalized)
        if handler:
            handler(user_id)
        else:
            self.send(
                user_id,
                "Пожалуйста, выберите действие с помощью кнопок.",
                main_keyboard(self.is_admin(user_id)),
            )

    def materials(self, user_id: int) -> None:
        rows = self.db.list_materials()
        if not rows:
            self.send(
                user_id,
                "Каталог наполняется. Пока вы можете оставить заявку на нужный материал.",
                back_keyboard(),
            )
            return
        for item in rows:
            self.send(
                user_id,
                f"{item['title']}\nУровень: {item['level']}\n{item['description']}",
            )
        self.send(user_id, "Это все доступные материалы.", back_keyboard())

    def new_request(self, user_id: int) -> None:
        if not self.ai.available:
            self.send(user_id, "ИИ для заявок пока не подключён.", back_keyboard())
            return
        self.interviews[user_id] = {"history": [], "questions": 0, "summary": ""}
        self.states[user_id] = "request_interview"
        self.send(
            user_id,
            "Опишите, какой материал вы хотите получить. Можно написать свободно — ИИ уточнит только недостающие детали.",
            back_keyboard(),
        )

    def continue_interview(self, user_id: int, text: str) -> None:
        interview = self.interviews[user_id]
        interview["history"].append({"role": "user", "content": text.strip()})
        self.send(user_id, "Анализирую ответ…")
        try:
            result = self.ai.continue_request_interview(
                interview["history"], interview["questions"]
            )
        except Exception:
            logger.exception("Request interview failed")
            self.send(
                user_id,
                "Не удалось обратиться к ИИ. Ваш диалог не отправлен как заявка. Попробуйте ещё раз позднее.",
                back_keyboard(),
            )
            return
        if result["status"] == "question" and interview["questions"] < 3:
            question = result["message"]
            interview["history"].append({"role": "assistant", "content": question})
            interview["questions"] += 1
            self.send(user_id, question, back_keyboard())
            return
        summary = result.get("summary", "").strip()
        if not summary:
            self.send(user_id, "ИИ не смог составить итог. Дополните описание.", back_keyboard())
            return
        interview["summary"] = summary
        self.states[user_id] = "request_confirmation"
        self.send(
            user_id,
            f"Проверьте итог заявки:\n\n{summary}",
            request_confirmation_keyboard(),
        )

    def confirm_request(self, user_id: int, action: str) -> None:
        interview = self.interviews.get(user_id)
        if not interview:
            self.show_menu(user_id)
        elif action == "подтвердить заявку":
            request_id = self.db.add_request(user_id, interview["summary"])
            self.interviews.pop(user_id, None)
            self.states.pop(user_id, None)
            self.send(
                user_id,
                f"Заявка №{request_id} принята. Я сообщу, когда её статус изменится.",
                main_keyboard(self.is_admin(user_id)),
            )
        elif action == "изменить заявку":
            self.states[user_id] = "request_interview"
            self.send(user_id, "Напишите, что нужно изменить или добавить.", back_keyboard())
        elif action == "отменить заявку":
            self.show_menu(user_id)
        else:
            self.send(user_id, "Выберите действие с помощью кнопок.", request_confirmation_keyboard())

    def start_ai(self, user_id: int, state: str) -> None:
        self.states[user_id] = state
        prompt = (
            "Опишите тему, уровень, возраст и желаемый тип упражнения."
            if state == "ai_task"
            else "Опишите тему урока, уровень, возраст и продолжительность занятия."
        )
        self.send(user_id, prompt, back_keyboard())

    def my_requests(self, user_id: int) -> None:
        rows = self.db.list_user_requests(user_id)
        if not rows:
            text = "У вас пока нет заявок."
        else:
            labels = {"new": "новая", "in_progress": "в работе", "done": "готово"}
            text = "Ваши последние заявки:\n\n" + "\n\n".join(
                f"№{row['id']} — {labels.get(row['status'], row['status'])}\n{row['text']}"
                for row in rows
            )
        self.send(user_id, text, back_keyboard())

    def subscription(self, user_id: int) -> None:
        self.send(
            user_id,
            "Подпишитесь, чтобы получать новые материалы и новости проекта.",
            subscription_keyboard(),
        )

    def change_subscription(self, user_id: int, subscribed: bool) -> None:
        self.db.set_subscription(user_id, subscribed)
        text = "Вы подписаны на рассылку." if subscribed else "Вы отписались от рассылки."
        self.send(user_id, text, main_keyboard(self.is_admin(user_id)))

    def contact(self, user_id: int) -> None:
        self.send(
            user_id,
            "Связаться с автором: https://vk.ru/turkcemateryaller",
            back_keyboard(),
        )

    def admin(self, user_id: int) -> None:
        if not self.is_admin(user_id):
            self.show_menu(user_id)
            return
        self.send(user_id, "Администраторский раздел подключён.", back_keyboard())

    def poll_once(self) -> None:
        updates = self.call(
            "getUpdates", offset=self.offset, timeout=25, allowed_updates=["message"]
        )
        for update in updates or []:
            self.offset = max(self.offset, int(update["update_id"]) + 1)
            self.process_update(update)

    def process_update(self, update: dict) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if chat.get("type") != "private" or "text" not in message:
            return
        try:
            self.handle(int(sender["id"]), str(message["text"]))
        except Exception:
            logger.exception("Message handling failed")

    def run_webhook(self, base_url: str) -> None:
        app = Flask(__name__)
        secret = hashlib.sha256(
            self.settings.telegram_bot_token.encode("utf-8")
        ).hexdigest()

        @app.get("/")
        def health():
            return {"status": "ok", "bot": "TurkceMateryallerAIBot"}

        @app.post("/telegram-webhook")
        def telegram_webhook():
            if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
                abort(403)
            update = request.get_json(silent=True) or {}
            threading.Thread(
                target=self.process_update, args=(update,), daemon=True
            ).start()
            return {"ok": True}

        webhook_url = f"{base_url.rstrip('/')}/telegram-webhook"
        self.call(
            "setWebhook",
            url=webhook_url,
            secret_token=secret,
            allowed_updates=["message"],
            drop_pending_updates=True,
        )
        logger.info("Telegram webhook configured: %s", webhook_url)
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))

    def run(self) -> None:
        identity = self.call("getMe")
        logger.info("Telegram bot started: @%s", identity.get("username", "unknown"))
        webhook_base_url = os.getenv("WEBHOOK_BASE_URL", "").strip()
        if webhook_base_url:
            self.run_webhook(webhook_base_url)
            return
        while True:
            try:
                self.poll_once()
            except Exception:
                logger.exception("Telegram polling failed")
                time.sleep(5)


if __name__ == "__main__":
    TelegramBot().run()
