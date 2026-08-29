from __future__ import annotations

import json

import requests


SYSTEM_PROMPT = """Ты методический помощник преподавателей турецкого языка.
Работай только с уровнями A0-A2. Пиши по-русски, а примеры давай на корректном
турецком языке. Не выдумывай источники, готовые файлы, цены, сроки или наличие
материалов. Не запрашивай и не включай в ответы персональные данные учеников."""


class AIService:
    def __init__(self, api_key: str | None, model: str):
        self.api_key = api_key
        self.model = model

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _generate(self, prompt: str, *, json_mode: bool = False) -> str:
        if not self.api_key:
            raise RuntimeError("Gemini API is not configured")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        body: dict = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        response = requests.post(
            url,
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            json=body,
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Gemini returned an unexpected response") from error

    def generate(self, request: str, kind: str) -> str:
        prompt = (
            f"Создай {kind} по запросу преподавателя. Учитывай уровень A0-A2, "
            f"возраст и цель урока. Запрос: {request}"
        )
        return self._generate(prompt)

    def continue_request_interview(
        self, history: list[dict[str, str]], questions_asked: int
    ) -> dict[str, str]:
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
        raw = self._generate(prompt, json_mode=True)
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError("Gemini returned invalid interview JSON") from error
        if result.get("status") == "question" and result.get("message"):
            return {"status": "question", "message": str(result["message"]).strip()}
        if result.get("status") == "ready" and result.get("summary"):
            return {"status": "ready", "summary": str(result["summary"]).strip()}
        raise RuntimeError("Gemini returned an unsupported interview result")
