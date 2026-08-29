from __future__ import annotations


def _keyboard(rows: list[list[str]]) -> dict:
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


def main_keyboard(is_admin: bool = False) -> dict:
    rows = [
        ["Найти материал", "Заказать материал"],
        ["Создать задание с ИИ", "План урока"],
        ["Мои заявки", "Рассылка"],
        ["Связаться с автором"],
    ]
    if is_admin:
        rows.append(["Администратор"])
    return _keyboard(rows)


def back_keyboard() -> dict:
    return _keyboard([["В главное меню"]])


def subscription_keyboard() -> dict:
    return _keyboard([["Подписаться", "Отписаться"], ["В главное меню"]])


def request_confirmation_keyboard() -> dict:
    return _keyboard([
        ["Подтвердить заявку", "Изменить заявку"],
        ["Отменить заявку", "В главное меню"],
    ])
