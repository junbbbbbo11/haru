"""AI 호출 모듈.

다른 AI(Claude, Gemini 등)로 바꾸고 싶으면 이 파일에 같은 모양의 클래스를 하나 더 만들고
make_client()에서 config.yaml의 ai.provider 값에 따라 골라 주면 된다.
나머지 코드는 complete_json(system, user) → dict 만 사용한다.
"""
import json
import logging
import os
import threading

log = logging.getLogger("haru.ai")


class AIError(Exception):
    """AI 응답이 이상함 (다시 시켜볼 만함)."""


class AICallError(AIError):
    """AI 서버 호출 자체가 실패 (키 오류, 잔액 부족, 네트워크 등 — 다시 해도 소용없음)."""


class OpenAIClient:
    """OpenAI Chat Completions + JSON 모드."""

    def __init__(self, model: str, api_key: str, reasoning_effort: str | None = None, timeout: int = 120):
        from openai import OpenAI

        self.model = model
        self.reasoning_effort = reasoning_effort
        self.client = OpenAI(api_key=api_key, timeout=timeout, max_retries=2)
        self._lock = threading.Lock()
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def complete_json(self, system: str, user: str) -> dict:
        extra = {}
        # 추론형 모델(gpt-5 계열, o 계열)은 추론 강도를 지정할 수 있다
        if self.reasoning_effort and self.model.startswith(("gpt-5", "o")):
            extra["reasoning_effort"] = self.reasoning_effort
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_object"},
                **extra,
            )
        except Exception as e:
            raise AICallError(f"OpenAI 호출 실패: {e}") from e

        if resp.usage:
            with self._lock:
                self.usage["calls"] += 1
                self.usage["input_tokens"] += resp.usage.prompt_tokens or 0
                self.usage["output_tokens"] += resp.usage.completion_tokens or 0

        text = resp.choices[0].message.content or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise AIError(f"AI 응답이 JSON이 아님: {text[:200]}") from e
        if not isinstance(data, dict):
            raise AIError("AI 응답이 JSON 객체가 아님")
        return data


def make_client(ai_cfg: dict):
    """설정과 환경변수를 보고 AI 클라이언트를 만든다. 쓸 수 없으면 None."""
    if not ai_cfg.get("enabled", True):
        log.info("AI 편집 꺼짐(config.yaml) → 원문 헤드라인으로 발행")
        return None
    provider = ai_cfg.get("provider", "openai")
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            log.warning("OPENAI_API_KEY 환경변수가 없음 → 원문 헤드라인으로 발행")
            return None
        return OpenAIClient(
            model=ai_cfg.get("model", "gpt-5-mini"),
            api_key=key,
            reasoning_effort=ai_cfg.get("reasoning_effort"),
            timeout=ai_cfg.get("timeout_seconds", 120),
        )
    log.warning("알 수 없는 AI provider '%s' → 원문 헤드라인으로 발행", provider)
    return None
