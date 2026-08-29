from __future__ import annotations

import logging
import random

import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll

from ai_service import AIService
from config import load_settings
from database import Database
from keyboards import (
    back_keyboard,
    main_keyboard,
    request_confirmation_keyboard,
    subscription_keyboard,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("turkce_bot")


class TurkceBot:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.session = vk_api.VkApi(token=self.settings.vk_group_token)
        self.api = self.session.get_api()
        self._log_vk_token_diagnostics()
        self.longpoll = VkBotLongPoll(self.session, self.settings.vk_group_id)
        self.db = Database(self.settings.database_path)
        self.db.initialize()
        self.ai = AIService(self.settings.openai_api_key, self.settings.openai_model)
        self.states: dict[int, str] = {}
        self.request_interviews: dict[int, dict] = {}

    def _log_vk_token_diagnostics(self) -> None:
        """Log non-secret token metadata before opening Long Poll."""
        try:
            result = self.api.groups.getTokenPermissions()
            permissions = [
                item.get("name", "unknown")
                for item in result.get("permissions", [])
                if isinstance(item, dict)
            ]
            logger.info("VK token permissions: %s", ", ".join(permissions) or "none")
        except Exception:
            logger.exception("Could not inspect VK token permissions")

        try:
            groups = self.api.groups.getById(group_id=self.settings.vk_group_id)
            resolved = groups.get("groups", groups) if isinstance(groups, dict) else groups
            logger.info("VK token group check: configured=%s resolved=%s", self.settings.vk_group_id, resolved)
        except Exception:
            logger.exception("Could not verify VK group for token")

    def send(self, user_id: int, text: str, keyboard=None, attachment: str | None = None) -> None:
        params = {
            "user_id": user_id,
            "message": text,
            "random_id": random.randint(1, 2_147_483_647),
        }
        if keyboard:
            params["keyboard"] = keyboard.get_keyboard()
        if attachment:
            params["attachment"] = attachment
        self.api.messages.send(**params)

    def show_menu(self, user_id: int) -> None:
        self.states.pop(user_id, None)
        self.request_interviews.pop(user_id, None)
        self.send(
            user_id,
            "Выберите нужный раздел:",
            main_keyboard(user_id == self.settings.admin_vk_id),
        )

    def handle_message(self, user_id: int, text: str) -> None:
        normalized = text.strip().lower()
        self.db.ensure_user(user_id)

        if normalized in {"начать", "старт", "в главное меню", "меню"}:
            self.show_menu(user_id)
            return

        state = self.states.get(user_id)
        if state == "request_interview":
            self.continue_request_interview(user_id, text)
            return
        if state == "request_confirmation":
            if normalized == "подтвердить заявку":
                interview = self.request_interviews.pop(user_id)
                request_id = self.db.add_request(user_id, interview["summary"])
                self.states.pop(user_id, None)
                self.send(
                    user_id,
                    f"Заявка №{request_id} принята. Я сообщу, когда её статус изменится.",
                    main_keyboard(user_id == self.settings.admin_vk_id),
                )
            elif normalized == "изменить заявку":
                self.states[user_id] = "request_interview"
                self.send(
                    user_id,
                    "Напишите, что нужно изменить или добавить. ИИ обновит итог заявки.",
                    back_keyboard(),
                )
            elif normalized == "отменить заявку":
                self.request_interviews.pop(user_id, None)
                self.show_menu(user_id)
            else:
                self.send(user_id, "Выберите: подтвердить, изменить или отменить заявку.", request_confirmation_keyboard())
            return
        if state in {"ai_task", "ai_lesson"}:
            kind = "упражнение с ответами" if state == "ai_task" else "план урока"
            self.send(user_id, "Готовлю результат…")
            try:
                result = self.ai.generate(text, kind)
            except Exception:
                logger.exception("AI request failed")
                result = "Не удалось получить ответ ИИ. Попробуйте ещё раз позднее."
            self.states.pop(user_id, None)
            self.send(user_id, result, main_keyboard(user_id == self.settings.admin_vk_id))
            return

        commands = {
            "найти материал": self.handle_materials,
            "заказать материал": self.handle_new_request,
            "создать задание с ии": lambda uid: self.start_ai(uid, "ai_task"),
            "план урока": lambda uid: self.start_ai(uid, "ai_lesson"),
            "мои заявки": self.handle_my_requests,
            "рассылка": self.handle_subscription,
            "подписаться": lambda uid: self.change_subscription(uid, True),
            "отписаться": lambda uid: self.change_subscription(uid, False),
            "связаться с автором": self.handle_contact,
            "администратор": self.handle_admin,
        }
        handler = commands.get(normalized)
        if handler:
            handler(user_id)
        else:
            self.send(user_id, "Пожалуйста, выберите действие с помощью кнопок.", main_keyboard())

    def handle_materials(self, user_id: int) -> None:
        materials = self.db.list_materials()
        if not materials:
            self.send(
                user_id,
                "Каталог наполняется. Пока вы можете оставить заявку на нужный материал.",
                back_keyboard(),
            )
            return
        for item in materials:
            description = f"{item['title']}\nУровень: {item['level']}\n{item['description']}"
            self.send(user_id, description, attachment=item["file_attachment"])
        self.send(user_id, "Это все доступные материалы.", back_keyboard())

    def handle_new_request(self, user_id: int) -> None:
        if not self.ai.available:
            self.send(
                user_id,
                "ИИ для оформления заявок пока не подключён. Попробуйте позднее или свяжитесь с автором.",
                back_keyboard(),
            )
            return
        self.request_interviews[user_id] = {"history": [], "questions": 0, "summary": ""}
        self.states[user_id] = "request_interview"
        self.send(
            user_id,
            "Опишите, какой материал вы хотите получить. Можно написать свободно — ИИ уточнит только недостающие детали.",
            back_keyboard(),
        )

    def continue_request_interview(self, user_id: int, text: str) -> None:
        interview = self.request_interviews[user_id]
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
            self.send(user_id, "ИИ не смог составить итог заявки. Попробуйте дополнить описание.", back_keyboard())
            return
        interview["summary"] = summary
        self.states[user_id] = "request_confirmation"
        self.send(
            user_id,
            f"Проверьте итог заявки:\n\n{summary}",
            request_confirmation_keyboard(),
        )

    def start_ai(self, user_id: int, state: str) -> None:
        self.states[user_id] = state
        prompt = (
            "Опишите тему, уровень, возраст и желаемый тип упражнения."
            if state == "ai_task"
            else "Опишите тему урока, уровень, возраст и продолжительность занятия."
        )
        self.send(user_id, prompt, back_keyboard())

    def handle_my_requests(self, user_id: int) -> None:
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

    def handle_subscription(self, user_id: int) -> None:
        self.send(
            user_id,
            "Подпишитесь, чтобы получать новые материалы и новости проекта.",
            subscription_keyboard(),
        )

    def change_subscription(self, user_id: int, subscribed: bool) -> None:
        self.db.set_subscription(user_id, subscribed)
        text = "Вы подписаны на рассылку." if subscribed else "Вы отписались от рассылки."
        self.send(user_id, text, main_keyboard(user_id == self.settings.admin_vk_id))

    def handle_contact(self, user_id: int) -> None:
        self.send(
            user_id,
            "Напишите вопрос следующим сообщением. В первой версии сообщения можно также отправить администратору сообщества вручную.",
            back_keyboard(),
        )

    def handle_admin(self, user_id: int) -> None:
        if user_id != self.settings.admin_vk_id:
            self.show_menu(user_id)
            return
        self.send(
            user_id,
            "Администраторский раздел подключён. Управление каталогом и рассылками добавим в следующем этапе.",
            back_keyboard(),
        )

    def run(self) -> None:
        logger.info("Bot started for group %s", self.settings.vk_group_id)
        for event in self.longpoll.listen():
            if event.type != VkBotEventType.MESSAGE_NEW:
                continue
            message = event.object.message
            if message.get("peer_id") != message.get("from_id"):
                continue
            try:
                self.handle_message(int(message["from_id"]), message.get("text", ""))
            except Exception:
                logger.exception("Message handling failed")


if __name__ == "__main__":
    TurkceBot().run()
