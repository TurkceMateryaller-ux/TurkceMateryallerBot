from __future__ import annotations

from openai import OpenAI


SYSTEM_PROMPT = """Ты методический помощник преподавателей турецкого языка.
Работай только с уровнями A0-A2. Пиши по-русски, а примеры давай на корректном
турецком языке. Не выдумывай источники, готовые файлы, цены или наличие
материалов. Учитывай возраст учеников и всегда добавляй ключ ответов, если
пользователь просит упражнение."""


class AIService:
    def __init__(self, api_key: str | None, model: str):
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = model

    def generate(self, request: str, kind: str) -> str:
        if not self.client:
            return (
                "ИИ пока не подключён. Ваш запрос сохранён в диалоге; "
                "после добавления OPENAI_API_KEY функция станет доступна."
            )
        instructions = SYSTEM_PROMPT + f"\nТип результата: {kind}."
        response = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=request,
        )
        return response.output_text.strip()

