"""AI 호출 모듈.

기본은 Pollinations 텍스트 API (무료, 가입·키 필요 없음). 무료 등급은 15초에 한 번만
요청할 수 있어서 호출 간격을 자동으로 맞춘다 (하루 12번 호출 → 3~4분).
OPENAI_API_KEY 를 등록하면 그때부터는 유료 OpenAI API를 쓴다 (provider: auto 일 때).

다른 AI(Claude, Gemini 등)로 바꾸고 싶으면 이 파일에 같은 모양의 클래스를 하나 더 만들고
make_client()에서 config.yaml의 ai.provider 값에 따라 골라 주면 된다.
나머지 코드는 complete_json(system, user) → dict 만 사용한다.
"""
import json
import logging
import os
import re
import threading
import time

log = logging.getLogger("haru.ai")

GITHUB_MODELS_URL = "https://models.github.ai/inference"
POLLINATIONS_URL = "https://text.pollinations.ai/openai"


class AIError(Exception):
    """AI 응답이 이상함 (다시 시켜볼 만함)."""


class AICallError(AIError):
    """AI 서버 호출 자체가 실패 (키 오류, 잔액 부족, 네트워크 등 — 다시 해도 소용없음)."""


class AITimeBudgetExceeded(AIError):
    """오늘 AI 편집에 쓸 시간을 다 씀 — 남은 부분은 원문 헤드라인으로."""


def _parse_json(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # ```json ... ``` 처럼 감싸서 답하는 경우 대비
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise AIError(f"AI 응답이 JSON이 아님: {text[:200]}")
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise AIError(f"AI 응답이 JSON이 아님: {text[:200]}") from e
    if not isinstance(data, dict):
        raise AIError("AI 응답이 JSON 객체가 아님")
    return data


class OpenAICompatibleClient:
    """OpenAI Chat Completions 형식의 API (OpenAI, GitHub Models) + JSON 모드."""

    def __init__(self, name: str, model: str, api_key: str, base_url: str | None = None,
                 reasoning_effort: str | None = None, timeout: int = 120,
                 max_workers: int = 5, prompt_candidates: int = 25, snippet_chars: int = 200,
                 json_mode: bool = True, min_interval: float = 0.0, max_tokens: int | None = None):
        from openai import OpenAI

        self.name = name
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=3)
        # 무료 한도(동시 요청 수·요청당 토큰)에 맞추기 위한 값들 — editor.py가 읽는다
        self.max_workers = max_workers
        self.prompt_candidates = prompt_candidates
        self.snippet_chars = snippet_chars
        self.json_mode = json_mode
        self.max_tokens = max_tokens
        self.deadline: float | None = None        # time.monotonic() 기준 마감 시각 (run.py가 정함)
        self.min_interval = min_interval          # 요청 사이 최소 간격(초) — 무료 등급 속도 제한
        self._last_call = 0.0
        self._gate = threading.Lock()
        self._lock = threading.Lock()
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def complete_json(self, system: str, user: str) -> dict:
        extra = {}
        # 추론형 모델(gpt-5 계열, o 계열)은 추론 강도를 지정할 수 있다
        bare = self.model.split("/")[-1]
        if self.reasoning_effort and bare.startswith(("gpt-5", "o")):
            extra["reasoning_effort"] = self.reasoning_effort
        if self.json_mode:
            extra["response_format"] = {"type": "json_object"}
        if self.max_tokens:
            extra["max_tokens"] = self.max_tokens
        with self._gate:  # 간격 제한이 있으면 한 번에 하나씩, 정해진 간격을 두고 보낸다
            for empty_try in range(3):  # 무료 등급은 가끔 빈 응답을 준다 → 간격을 두고 다시
                wait = self._last_call + self.min_interval - time.monotonic()
                if self.deadline and time.monotonic() + max(wait, 0) > self.deadline:
                    raise AITimeBudgetExceeded("AI 편집 시간 상한 도달")
                if wait > 0:
                    time.sleep(wait)
                try:
                    resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                        **extra,
                    )
                except Exception as e:
                    raise AICallError(f"{self.name} 호출 실패: {e}") from e
                finally:
                    self._last_call = time.monotonic()
                if getattr(resp, "choices", None) and (resp.choices[0].message.content or "").strip():
                    break
                log.info("    (빈 응답 → 다시 요청 %d)", empty_try + 1)

        if getattr(resp, "usage", None):
            with self._lock:
                self.usage["calls"] += 1
                self.usage["input_tokens"] += resp.usage.prompt_tokens or 0
                self.usage["output_tokens"] += resp.usage.completion_tokens or 0
        if not getattr(resp, "choices", None):
            raise AIError(f"{self.name} 응답에 내용이 없음")
        return _parse_json(resp.choices[0].message.content or "")


# 하위 호환
OpenAIClient = OpenAICompatibleClient


def make_client(ai_cfg: dict):
    """설정과 환경변수를 보고 AI 클라이언트를 만든다. 쓸 수 없으면 None."""
    if not ai_cfg.get("enabled", True):
        log.info("AI 편집 꺼짐(config.yaml) → 원문 헤드라인으로 발행")
        return None

    provider = ai_cfg.get("provider", "auto")
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    gh_token = os.environ.get("GITHUB_TOKEN", "").strip()
    if provider == "auto":
        provider = "openai" if openai_key else "pollinations"

    timeout = ai_cfg.get("timeout_seconds", 120)
    if provider == "openai":
        if not openai_key:
            log.warning("OPENAI_API_KEY 환경변수가 없음 → 원문 헤드라인으로 발행")
            return None
        model = ai_cfg.get("openai_model") or "gpt-5-mini"
        log.info("AI: OpenAI API (%s)", model)
        return OpenAICompatibleClient("OpenAI", model, openai_key,
                                      reasoning_effort=ai_cfg.get("reasoning_effort"), timeout=timeout)

    if provider == "github":
        if not gh_token:
            log.warning("GITHUB_TOKEN 이 없음(내 컴퓨터에서 실행 중?) → 원문 헤드라인으로 발행")
            return None
        model = ai_cfg.get("github_model") or "openai/gpt-4.1-mini"
        log.info("AI: GitHub Models 무료 (%s)", model)
        # 무료 등급: 동시 요청 수와 요청당 입력 토큰(약 8천)이 작아서 후보 수·요약문 길이를 줄인다
        return OpenAICompatibleClient("GitHub Models", model, gh_token, base_url=GITHUB_MODELS_URL,
                                      timeout=timeout, max_workers=2, prompt_candidates=15, snippet_chars=90)

    if provider == "pollinations":
        model = ai_cfg.get("pollinations_model") or "openai"
        log.info("AI: Pollinations 무료 (%s) — 15초 간격으로 차례대로 호출", model)
        return OpenAICompatibleClient("Pollinations", model, "none", base_url=POLLINATIONS_URL,
                                      timeout=timeout, max_workers=1, prompt_candidates=15, snippet_chars=90,
                                      json_mode=False, min_interval=float(ai_cfg.get("min_interval_seconds", 16)),
                                      max_tokens=3000)

    log.warning("알 수 없는 AI provider '%s' → 원문 헤드라인으로 발행", provider)
    return None
