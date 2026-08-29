from __future__ import annotations

import json

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

    @property
    def available(self) -> bool:
        return self.client is not None

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

    def continue_request_interview(
        self, history: list[dict[str, str]], questions_asked: int
    ) -> dict[str, str]:
        if not self.client:
            return {"status": "unavailable", "message": "ИИ пока не подключён."}

        prompt = f"""Проведи короткое интервью для заявки на учебный материал.
Целевая аудитория сервиса: преподаватели турецкого языка, уровни A0-A2.
Проанализируй весь диалог и реши, достаточно ли данных для технического задания.

Желательные сведения: тема, уровень, возраст учеников, тип материала, формат,
содержание заданий, цветная или чёрно-белая печать, необходимость ключа ответов,
дополнительные пожелания. Не спрашивай то, что уже понятно из диалога.

Уже задано уточняющих вопросов: {questions_asked}. Максимум: 3.
Если данных недостаточно и лимит не исчерпан, задай ровно один самый полезный
следующий вопрос. Если данных достаточно или лимит исчерпан, составь ясное
техническое задание. Не обещай цену, срок или готовность материала.

Верни только JSON одного из видов:
{{"status":"question","message":"один уточняющий вопрос"}}
{{"status":"ready","summary":"структурированное техническое задание"}}

Диалог:
{json.dumps(history, ensure_ascii=False)}
"""
        response = self.client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=prompt,
        )
        raw = response.output_text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].lstrip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError("AI returned invalid interview JSON") from error
        if result.get("status") == "question" and result.get("message"):
            return {"status": "question", "message": str(result["message"]).strip()}
        if result.get("status") == "ready" and result.get("summary"):
            return {"status": "ready", "summary": str(result["summary"]).strip()}
        raise RuntimeError("AI returned an unsupported interview result")
