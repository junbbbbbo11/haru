"""AI 호출 모듈.

provider: auto 일 때 쓸 수 있는 것을 우선순위대로 이어 붙인다 (앞의 것이 실패하면 자동으로 다음 것):
  1) OPENAI_API_KEY 가 있으면 OpenAI (유료)
  2) CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN 이 있으면 Cloudflare Workers AI (무료 한도 안에서 0원, 빠르고 안정적)
  3) 항상 마지막 보루로 Pollinations (무료, 가입·키 필요 없음, 15초에 한 번만 호출 가능해서 느림)

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
CLOUDFLARE_URL = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1"


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
                 json_mode: bool = True, min_interval: float = 0.0, max_tokens: int | None = None,
                 system_prefix: str = "", empty_backoff: float = 0.0):
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
        self.system_prefix = system_prefix        # 예: gpt-oss 계열은 "Reasoning: low" 로 생각을 짧게
        self.empty_backoff = empty_backoff        # 빈 응답(속도 제한)일 때 추가로 쉬는 시간(초)
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
                    try:
                        resp = self.client.chat.completions.create(
                            model=self.model,
                            messages=[{"role": "system", "content": self.system_prefix + system},
                                      {"role": "user", "content": user}],
                            **extra,
                        )
                    except Exception as e:
                        # JSON 모드(response_format)를 지원하지 않는 모델이면, 끄고 한 번 더 (프롬프트가 이미 JSON을 요구함)
                        if "response_format" in extra and getattr(e, "status_code", None) in (400, 422):
                            log.info("    (%s: JSON 모드 미지원 → 끄고 다시)", self.name)
                            self.json_mode = False
                            extra.pop("response_format", None)
                            resp = self.client.chat.completions.create(
                                model=self.model,
                                messages=[{"role": "system", "content": self.system_prefix + system},
                                          {"role": "user", "content": user}],
                                **extra,
                            )
                        else:
                            raise
                except Exception as e:
                    raise AICallError(f"{self.name} 호출 실패: {str(e)[:300]}") from e
                finally:
                    self._last_call = time.monotonic()
                if getattr(resp, "choices", None) and (resp.choices[0].message.content or "").strip():
                    break
                log.info("    (빈 응답 → 잠시 쉬고 다시 요청 %d)", empty_try + 1)
                self._last_call += self.empty_backoff

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


class ChainClient:
    """여러 AI를 우선순위대로 이어 붙인다. 호출 자체가 실패하면(키 오류·한도 초과·서버 오류) 다음 AI로 넘어간다.
    AI가 답은 줬는데 형식이 틀린 경우(AIError)는 그대로 올려 보내서, 편집 쪽의 '이유를 알려주고 다시' 로직이 처리한다."""

    def __init__(self, clients: list):
        self.clients = clients
        self._fails = [0] * len(clients)
        self._dead: set[int] = set()
        head = clients[0]
        self.max_workers = head.max_workers
        self.prompt_candidates = head.prompt_candidates
        self.snippet_chars = head.snippet_chars
        self.name = " → ".join(c.name for c in clients)

    @property
    def deadline(self):
        return self.clients[0].deadline

    @deadline.setter
    def deadline(self, value):
        for c in self.clients:
            c.deadline = value

    @property
    def usage(self) -> dict:
        total = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        for c in self.clients:
            for k in total:
                total[k] += c.usage.get(k, 0)
        return total

    def usage_by_provider(self) -> str:
        return ", ".join(f"{c.name} {c.usage['calls']}회" for c in self.clients if c.usage["calls"])

    def complete_json(self, system: str, user: str) -> dict:
        last = None
        for i, c in enumerate(self.clients):
            if i in self._dead:
                continue
            try:
                out = c.complete_json(system, user)
                self._fails[i] = 0
                return out
            except AITimeBudgetExceeded:
                raise
            except AICallError as e:
                last = e
                self._fails[i] += 1
                fatal = any(k in str(e) for k in ("401", "403", "Unauthorized", "authentication", "Invalid", "insufficient", "quota", "4006", "429"))
                if fatal or self._fails[i] >= 3:
                    self._dead.add(i)
                    log.warning("    ✗ %s 사용 중단(%s) → 다음 AI로", c.name, str(e)[:120])
                else:
                    log.warning("    ✗ %s 호출 실패 → 이번 요청은 다음 AI로: %s", c.name, str(e)[:120])
        raise AICallError(f"모든 AI 호출 실패: {last}")


def _openai(ai_cfg: dict, key: str, timeout: int):
    model = ai_cfg.get("openai_model") or "gpt-5-mini"
    log.info("AI: OpenAI API (%s)", model)
    return OpenAICompatibleClient("OpenAI", model, key,
                                  reasoning_effort=ai_cfg.get("reasoning_effort"), timeout=timeout)


def _cloudflare(ai_cfg: dict, account: str, token: str, timeout: int, model: str | None = None):
    model = model or ai_cfg.get("cloudflare_model") or "@cf/openai/gpt-oss-120b"
    log.info("AI: Cloudflare Workers AI 무료 (%s)", model)
    return OpenAICompatibleClient("Cloudflare", model, token, base_url=CLOUDFLARE_URL.format(account=account),
                                  timeout=timeout, max_workers=3, prompt_candidates=25, snippet_chars=200,
                                  system_prefix="Reasoning: low\n")


def _pollinations(ai_cfg: dict, timeout: int):
    model = ai_cfg.get("pollinations_model") or "openai"
    log.info("AI: Pollinations 무료 (%s) — 18초 간격으로 차례대로 호출", model)
    # 무료 모델(gpt-oss)은 추론형이라 'Reasoning: low' 로 생각을 짧게 하고, 질문도 짧게 줄인다
    return OpenAICompatibleClient("Pollinations", model, "none", base_url=POLLINATIONS_URL,
                                  timeout=timeout, max_workers=1, prompt_candidates=10, snippet_chars=60,
                                  json_mode=False, min_interval=float(ai_cfg.get("min_interval_seconds", 18)),
                                  system_prefix="Reasoning: low\n", empty_backoff=30)


def make_client(ai_cfg: dict):
    """설정과 환경변수를 보고 AI 클라이언트를 만든다. 쓸 수 없으면 None."""
    if not ai_cfg.get("enabled", True):
        log.info("AI 편집 꺼짐(config.yaml) → 원문 헤드라인으로 발행")
        return None

    provider = ai_cfg.get("provider", "auto")
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    cf_account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    cf_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    timeout = ai_cfg.get("timeout_seconds", 120)

    if provider == "auto":
        chain = []
        if openai_key:
            chain.append(_openai(ai_cfg, openai_key, timeout))
        if cf_account and cf_token:
            chain.append(_cloudflare(ai_cfg, cf_account, cf_token, timeout))
            second = ai_cfg.get("cloudflare_model_backup")
            if second:
                chain.append(_cloudflare(ai_cfg, cf_account, cf_token, timeout, second))
        chain.append(_pollinations(ai_cfg, timeout))
        return chain[0] if len(chain) == 1 else ChainClient(chain)

    if provider == "openai":
        if not openai_key:
            log.warning("OPENAI_API_KEY 환경변수가 없음 → 원문 헤드라인으로 발행")
            return None
        return _openai(ai_cfg, openai_key, timeout)
    if provider == "cloudflare":
        if not (cf_account and cf_token):
            log.warning("CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN 이 없음 → 원문 헤드라인으로 발행")
            return None
        return _cloudflare(ai_cfg, cf_account, cf_token, timeout)
    if provider == "pollinations":
        return _pollinations(ai_cfg, timeout)

    log.warning("알 수 없는 AI provider '%s' → 원문 헤드라인으로 발행", provider)
    return None
