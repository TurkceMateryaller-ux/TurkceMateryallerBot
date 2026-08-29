from __future__ import annotations

from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def main_keyboard(is_admin: bool = False) -> VkKeyboard:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Найти материал", VkKeyboardColor.PRIMARY)
    keyboard.add_button("Заказать материал", VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Создать задание с ИИ", VkKeyboardColor.POSITIVE)
    keyboard.add_button("План урока", VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("Мои заявки", VkKeyboardColor.SECONDARY)
    keyboard.add_button("Рассылка", VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("Связаться с автором", VkKeyboardColor.SECONDARY)
    if is_admin:
        keyboard.add_line()
        keyboard.add_button("Администратор", VkKeyboardColor.NEGATIVE)
    return keyboard


def back_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("В главное меню", VkKeyboardColor.SECONDARY)
    return keyboard


def subscription_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Подписаться", VkKeyboardColor.POSITIVE)
    keyboard.add_button("Отписаться", VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("В главное меню", VkKeyboardColor.SECONDARY)
    return keyboard


def request_confirmation_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Подтвердить заявку", VkKeyboardColor.POSITIVE)
    keyboard.add_button("Изменить заявку", VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Отменить заявку", VkKeyboardColor.NEGATIVE)
    keyboard.add_button("В главное меню", VkKeyboardColor.SECONDARY)
    return keyboard
