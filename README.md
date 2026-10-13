# 하루 한 장

매일 아침 7시 전에 자동으로 뉴스를 모으고 AI가 요약해서, 패션 매거진처럼 디자인된 한 페이지를 발행하는 개인 뉴스 사이트입니다.

- **주소 하나로 항상 최신호**: `https://내아이디.github.io/저장소이름/`
- **오늘의 OOTD**: 그날 날씨와 패션 뉴스를 보고 AI가 **여성·남성 한 벌씩** 추천하고, 그 옷을 입은 **목 아래 실사 착샷**을 AI로 생성 (무료). 페이지에서 여성 | 남성 탭으로 골라 봅니다
- **지난 호**: 페이지 맨 아래 "어제 호 / 지난 호 보기"
- **아침에 훑기 좋게**: 상단 읽기 진행 막대, 섹션 바로가기 탭, 기사마다 "OO 외 N곳 보도"(화제성), 지표 7일 추이 그래프,
  운세는 내 띠를 한 번 누르면 다음부터 그것만 크게, 휴대폰 공유 버튼, 다크모드
- **홈 화면 앱**: 휴대폰 홈 화면에 추가하면 "한" 아이콘으로 앱처럼 열립니다 (항상 최신호)
- **인스타그램 카드뉴스**: 매일 1080×1350 카드 7~8장 + 캡션이 자동으로 만들어집니다 → `주소/cards/`
- **비용: 0원.** 가입·카드 등록·API 키 없이 동작합니다 (AI 요약 = Pollinations 무료, 착샷 = Hugging Face 무료)
- **지금 발행 중인 주소**: https://junbbbbbo11.github.io/haru/

---

## 목차
1. [처음 설정하기 (딱 한 번, 약 20분)](#1-처음-설정하기)
2. [이메일로 매일 링크 받기 (선택)](#2-이메일로-매일-링크-받기-선택)
   · [(선택) 착샷을 더 안정적으로](#1-7-선택-착샷을-더-안정적으로--cloudflare-무료-계정)
3. [뉴스 소스 추가/삭제하기](#3-뉴스-소스-추가삭제하기)
4. [발행 시간 바꾸기](#4-발행-시간-바꾸기)
5. [그 밖의 설정 바꾸기](#5-그-밖의-설정-바꾸기)
6. [문제가 생겼을 때](#6-문제가-생겼을-때)
7. [내 컴퓨터에서 실행해 보기](#7-내-컴퓨터에서-실행해-보기)
8. [어떻게 동작하나요?](#8-어떻게-동작하나요)

---

## 1. 처음 설정하기

### 1-1. AI는 무료로 자동 설정됩니다 (할 일 없음)

- **AI 요약·커버 선정·OOTD 추천**: Pollinations 무료 텍스트 API — 가입·키 없이 동작합니다.
  무료 등급은 15초에 한 번만 부를 수 있어서, 발행에 5~15분쯤 걸립니다 (아침 06:40 시작 → 07시 전후 완성).
- **OOTD 착샷**: Hugging Face 공개 Space(FLUX) — 가입·키 없이 동작합니다.
- 무료 서비스라 가끔 실패할 수 있습니다. 그래도 발행은 멈추지 않고, 실패한 부분만 원문 헤드라인·일러스트로 나옵니다.
- AI가 원문에 없는 숫자를 쓰면 자동으로 걸러 다시 쓰게 합니다 (무료 모델의 사실 오류 방지).

> 💡 **(선택) 더 좋게 만들고 싶다면**
> - 유료 OpenAI(월 1~2달러, 더 정확·빠름): https://platform.openai.com → API keys 에서 키를 만들어 Secrets에 `OPENAI_API_KEY` 로 등록하면 자동으로 OpenAI를 씁니다.
> - 착샷을 더 안정적으로(무료): 아래 1-7의 Cloudflare 무료 계정.

### 1-2. GitHub 저장소 만들기

1. https://github.com 에 가입/로그인합니다.
2. 오른쪽 위 **+** → **New repository**
3. 입력:
   - **Repository name**: `haru` (원하는 영어 이름. 이게 주소에 들어갑니다 → `https://내아이디.github.io/haru/`)
   - **Public** 선택 (무료 계정은 Public이어야 GitHub Pages가 무료입니다. 코드에 비밀값이 없으니 공개돼도 괜찮습니다)
   - 나머지는 그대로 두고 **Create repository**

### 1-3. 파일 올리기

**방법 A — 웹 브라우저로 끌어다 놓기 (가장 쉬움)**

1. 방금 만든 저장소 화면에서 **uploading an existing file** 링크를 누릅니다.
   (안 보이면 **Add file** → **Upload files**)
2. 이 프로젝트 폴더를 탐색기로 열고, 아래 항목들을 **전부 선택해서** 브라우저 창으로 끌어다 놓습니다.
   ```
   .github     ← 자동 실행 설정. 꼭 포함! (점으로 시작하는 폴더)
   haru
   templates
   .gitignore
   config.yaml
   quotes.yaml
   README.md
   requirements.txt
   run.py
   sources.yaml
   ```
   > 💡 `.github` 폴더가 탐색기에 안 보이면: 탐색기 위쪽 **보기** → **표시** → **숨긴 항목** 체크.
   > `data`, `site`, `logs` 폴더가 있다면 올리지 않아도 됩니다(자동으로 만들어집니다).
3. 업로드가 끝나면 아래 **Commit changes** 버튼을 누릅니다.
4. 저장소 첫 화면에 `.github` 폴더가 보이는지 확인하세요. 안 보이면 2번에서 빠진 것이니 다시 올립니다.

**방법 B — GitHub Desktop 프로그램** (앞으로 자주 고칠 거라면 편함)
https://desktop.github.com 설치 → **File → Add local repository** 로 이 폴더 선택 → "create a repository" 안내에 따라 만들고 → **Publish repository** (이때 **Keep this code private 체크 해제**).

### 1-4. (선택) API 키를 GitHub 금고(Secrets)에 넣기

키가 없어도 무료로 동작합니다. 유료 OpenAI나 Cloudflare를 쓰고 싶을 때만 하세요.


1. 저장소 화면 위쪽 탭 **Settings** (톱니바퀴)
2. 왼쪽 메뉴 **Secrets and variables** → **Actions**
3. 초록 버튼 **New repository secret**
4. **Name**: `OPENAI_API_KEY` (글자 그대로, 대문자)
   **Secret**: OpenAI에서 발급받은 `sk-...` 키 붙여넣기
5. **Add secret**

### 1-5. GitHub Pages 켜기

1. 저장소 **Settings** → 왼쪽 메뉴 **Pages**
2. **Build and deployment** 의 **Source** 를 **GitHub Actions** 로 바꿉니다. (저장 버튼은 따로 없습니다)

### 1-6. 첫 발행 (수동 실행)

1. 저장소 위쪽 탭 **Actions**
   - "Workflows aren't being run on this repository" 같은 안내가 나오면 **I understand my workflows, go ahead and enable them** 클릭
2. 왼쪽 목록에서 **하루 한 장 발행** 클릭
3. 오른쪽 **Run workflow** → 초록 **Run workflow** 버튼
4. 잠시 후 생기는 실행 항목을 누르면 진행 상황이 보입니다. 1~3분이면 초록 체크 ✅ 가 됩니다.
5. 완료 화면의 `publish` 상자에 나오는 링크(`https://내아이디.github.io/haru/`)가 내 매거진 주소입니다. 🎉
   휴대폰 홈 화면에 추가해 두면 앱처럼 쓸 수 있습니다.
   - **아이폰(사파리)**: 아래 가운데 공유 버튼 □↑ → **홈 화면에 추가**
   - **안드로이드(크롬)**: 오른쪽 위 ⋮ → **홈 화면에 추가** (또는 **앱 설치**)

이제 **매일 아침 06:40(한국 시간)쯤 자동으로 발행**됩니다.

### 1-7. (선택) 착샷을 더 안정적으로 — Cloudflare 무료 계정

건너뛰어도 착샷은 Hugging Face 무료 Space로 만들어집니다. 다만 공개 Space는 사람이 몰리면 실패할 때가 있어서, Cloudflare 키를 넣어 두면 Cloudflare를 먼저 쓰고 실패할 때만 Hugging Face로 넘어갑니다.
(이미지 AI **FLUX.1 schnell** 을 무료 한도 안에서 씁니다. 하루 2장(여성·남성)은 무료 한도의 몇 %도 안 됩니다. 카드 등록 필요 없음)

1. https://dash.cloudflare.com/sign-up 에서 이메일로 가입하고 메일 인증을 합니다.
2. 로그인 후 왼쪽 메뉴에서 **AI** → **Workers AI** 를 엽니다.
3. **Use REST API** 를 누르면 두 가지가 나옵니다.
   - **Account ID**: 옆의 복사 버튼으로 복사해 메모장에 붙여 둡니다.
   - **Create a Workers AI API Token** → 권한이 미리 채워진 화면에서 아래로 내려 **Create API Token** → 나온 토큰을 **Copy** (이 창을 닫으면 다시 볼 수 없습니다)
4. GitHub 저장소 **Settings → Secrets and variables → Actions → New repository secret** 으로 두 개를 추가합니다.

   | Name | Secret 값 |
   |---|---|
   | `CLOUDFLARE_ACCOUNT_ID` | 3번의 Account ID |
   | `CLOUDFLARE_API_TOKEN` | 3번의 토큰 |

5. Actions에서 **Run workflow** 로 수동 실행 → 로그에 `✓ [여성] 착샷 생성`, `✓ [남성] 착샷 생성` 이 나오면 성공입니다.

> 📸 착샷은 **목 아래만** 나옵니다. AI에게 목 아래 구도로 주문하고, 그래도 얼굴이 그려지면
> 얼굴 검출(OpenCV YuNet)로 찾아서 **턱 아래로 자동으로 잘라냅니다.** 잘라낸 사진에 얼굴이 또 보이거나
> 얼굴이 너무 커서 자를 수 없으면 버리고 다시 생성합니다(최대 3번, 그래도 안 되면 그날은 일러스트).
> 이미지에는 "AI로 생성한 이미지" 표시가 붙습니다.
> 옷은 AI가 사실적으로 그린 것이며 특정 브랜드 상품이 아닙니다. 가끔 손이나 소품이 어색하게 나오는 날이 있을 수 있습니다.

---

## 2. 이메일로 매일 링크 받기 (선택)

발행이 끝나면 "오늘의 하루 한 장" 제목으로 커버스토리 3줄과 링크를 메일로 보내 줍니다.

### 2-1. Gmail 앱 비밀번호 만들기
1. 보내는 데 쓸 Gmail로 https://myaccount.google.com 접속
2. **보안** → **2단계 인증** 을 켭니다 (이미 켜져 있으면 통과)
3. https://myaccount.google.com/apppasswords 접속 → 앱 이름 `haru` 입력 → **만들기**
4. 나오는 **16자리 비밀번호**를 복사합니다. (Gmail 로그인 비밀번호가 아닙니다)

### 2-2. Secrets 3개 추가 (1-4와 같은 화면)
| Name | Secret 값 |
|---|---|
| `GMAIL_ADDRESS` | 보내는 Gmail 주소 (예: `me@gmail.com`) |
| `GMAIL_APP_PASSWORD` | 2-1의 16자리 앱 비밀번호 |
| `MAIL_TO` | 받을 주소. 여러 명이면 쉼표로: `a@gmail.com,b@naver.com` (비우면 보내는 주소로) |

### 2-3. 기능 켜기
1. 저장소에서 `config.yaml` 파일 클릭 → 오른쪽 위 연필 ✏️ 아이콘
2. `email:` 아래 `enabled: false` 를 `enabled: true` 로 바꿉니다
3. **Commit changes...** → **Commit changes**
4. Actions에서 수동 실행해 보면 메일이 옵니다. (스팸함도 확인)

---

## 2-1. 인스타그램 카드뉴스

매일 발행할 때 카드뉴스도 함께 만들어집니다. 페이지 맨 아래 **오늘의 카드뉴스 보기 →** 또는 `https://내아이디.github.io/haru/cards/`

| 순서 | 카드 |
|---|---|
| 01 | 표지 — 제호, 날짜, 커버스토리 3줄 |
| 02~04 | 커버스토리 한 장씩 (헤드라인 + 요약 + 출처) |
| 05 | 섹션 브리핑 — 9개 섹션 한 줄씩 |
| 06~07 | 오늘의 OOTD — 여성 / 남성 착샷 (착샷이 없는 날은 일러스트 1장) |
| 마지막 | 오늘의 지표 + 명언 + 마무리 |

**올리는 법**: 카드뉴스 페이지에서 카드를 눌러 크게 열고 길게 눌러 **사진에 저장** → 인스타그램 **새 게시물 → 여러 장 선택** 에서 01번부터 순서대로 → 페이지 아래 **캡션 복사** 해서 붙여넣기.

- 카드뉴스는 **그날 것만** 사이트에 올라갑니다 (저장소 용량 때문에). 지난 카드가 필요하면 Actions 실행 화면의 **Artifacts → cards-...** 에서 30일 동안 내려받을 수 있습니다.
- 디자인은 `templates/cards.html` 에서 고칩니다. 끄려면 `config.yaml` 의 `cards.enabled: false`.

## 3. 뉴스 소스 추가/삭제하기

GitHub 웹에서 `sources.yaml` → 연필 ✏️ 로 바로 고칠 수 있습니다. 섹션마다 이렇게 생겼습니다.

```yaml
  - id: fashion
    name: 패션
    feeds:
      - name: VOGUE Korea                    # 화면에 표시될 매체 이름
        url: https://www.vogue.co.kr/feed/   # RSS 주소
    search:
      - 패션 브랜드                           # 구글 뉴스에서 이 단어로 검색
```

- **RSS 추가**: `- name:` 과 `url:` 두 줄을 복사해 아래에 붙이고 내용만 바꿉니다.
- **검색어 추가**: `search:` 아래에 `- 검색어` 한 줄 추가. (최근 24시간 구글 뉴스 검색 결과를 자동으로 가져옵니다. RSS 주소를 몰라도 되니 가장 쉬운 방법입니다)
- **삭제**: 해당 줄을 지우거나, 줄 맨 앞에 `#` 을 붙이면 꺼집니다.
- ⚠️ **들여쓰기(앞쪽 스페이스 개수)를 위아래 줄과 똑같이** 맞춰야 합니다. 탭 키 말고 스페이스를 쓰세요.
- 고친 뒤 Actions에서 수동 실행 → 로그에서 `✓ 새매체: N건` 이 보이면 성공, `✗ 새매체 실패` 면 주소가 틀린 것입니다.
  (소스 하나가 실패해도 발행은 멈추지 않습니다)

> 💡 RSS 주소 찾기: 언론사 사이트 맨 아래에서 "RSS" 링크를 찾거나, 구글에 `매체이름 RSS` 로 검색하세요.
> 날짜 정보가 없는 RSS(예: 한겨레)는 "최근 24시간" 판별이 불가능해서 자동으로 걸러집니다.

**오늘의 명언**은 `quotes.yaml` 에 있는 목록에서 날짜별로 하나씩 돌아갑니다. 같은 방법으로 추가할 수 있습니다.

---

## 4. 발행 시간 바꾸기

`.github/workflows/publish.yml` 파일의 이 부분을 고칩니다.

```yaml
  schedule:
    - cron: "40 21 * * *"     # 본 실행
    - cron: "10 22 * * *"     # 예비 실행 (본 실행이 빠졌을 때만 발행)
```

형식은 `"분 시 * * *"` 이고 **영국 시간(UTC) 기준**이라 **한국 시간에서 9시간을 뺍니다.**

| 원하는 한국 시간 | 적을 값 |
|---|---|
| 05:40 | `"40 20 * * *"` |
| 06:10 | `"10 21 * * *"` |
| **06:40 (기본)** | `"40 21 * * *"` |
| 07:30 | `"30 22 * * *"` |
| 08:00 | `"0 23 * * *"` |

- 예비 실행은 본 실행 **30분 뒤**로 맞춰 주세요.
- GitHub 예약 실행은 서버가 붐비면 **10~30분 늦게** 시작할 수 있습니다. 꼭 받아야 하는 시각보다 20~30분 일찍 잡으세요.
- 날짜는 한국 시간 기준으로 정해지므로, 새벽 0시 이후라면 몇 시에 돌려도 "오늘 호"가 됩니다.

---

## 5. 그 밖의 설정 바꾸기

모두 `config.yaml` 에서 바꿉니다.

| 항목 | 설명 |
|---|---|
| `site.title` | 매거진 제호 |
| `site.url` | 직접 산 도메인을 쓸 때만 적습니다. 비우면 GitHub 주소 자동 |
| `ai.model` | `gpt-5-mini`(기본·가성비) / `gpt-5`(더 잘 씀, 약 5배 비쌈) / `gpt-5-nano`(가장 쌈) |
| `ai.provider` | `auto`(기본: OpenAI 키가 있으면 OpenAI, 없으면 무료 Pollinations) / `pollinations` / `openai` |
| `ai.enabled` | `false` 면 AI 없이 원문 헤드라인으로만 발행 |
| `lookbook.providers` | 착샷 이미지 AI 시도 순서. 기본 `[cloudflare, hf_space]` (cloudflare 는 키가 있을 때만) |
| `collect.items_per_section` | 섹션마다 최대 몇 개 (1~2) |
| `collect.max_total_items` | 섹션 기사 전체 상한. 기본 13개 ≈ 3분 분량 |
| `ootd.enabled` | 오늘의 OOTD 켜기/끄기 |
| `weather.city` 등 | OOTD에 쓰는 날씨 지역. 다른 도시는 위도·경도도 함께 바꿉니다 (예: 부산 35.18 / 129.08) |
| `lookbook.enabled` | 착샷 켜기/끄기 (끄면 일러스트) |
| `lookbook.framing` | `street` = 거리 스냅(기본) / `studio` = 무지 배경 룩북. 어느 쪽이든 목 아래만 |
| `ootd.default` | 처음 열었을 때 보일 탭 (`women` / `men`). 한 번 누른 탭은 그 기기에서 기억됩니다 |
| `ootd.looks` 의 `style` | 추천받을 스타일. 예: `여성 오피스룩`, `남성 미니멀 캐주얼` |
| `ootd.looks` 의 `person` | 착샷 속 인물을 영어로. 예: `a woman in her 30s, 165cm, slim build` / `a man in his 20s, tall, athletic build` |
| `lookbook.keep_days` | 이 일수보다 오래된 착샷은 지워서 저장소 용량 관리 (기본 90일. 지난 호는 일러스트로 보임) |
| `email.enabled` | 이메일 발송 켜기/끄기 |

디자인은 `templates/` 폴더(`edition.html` 은 페이지 구조, `style.css` 는 색·글꼴·여백)를 고치면 됩니다.
섹션별 포인트 컬러와 지면 레이아웃은 `haru/render.py` 맨 위 `SECTION_STYLE` 에 있습니다.
디자인을 고치면 다음 발행 때 **지난 호들도 새 디자인으로** 다시 그려집니다.

---

## 6. 문제가 생겼을 때

**어디를 보나요?** 저장소 **Actions** 탭 → 해당 날짜 실행 → **publish** → **오늘 호 만들기** 를 펼치면 전체 로그가 있습니다.
(같은 실행 화면 아래 **Artifacts** 의 `log-...` 를 받으면 로그 파일도 있습니다. 30일 보관)

| 증상 | 원인과 해결 |
|---|---|
| 일부 섹션만 원문 헤드라인 | 무료 AI가 그 섹션에서 빈 응답을 주거나 검증(숫자·띄어쓰기·베끼기)에 걸린 것. 다음 날 보통 괜찮아집니다 |
| 페이지 상단에 "AI 편집 없이 원문 헤드라인으로 발행" | 로그에서 `OpenAI 호출 실패` 를 찾아보세요. `401` = 키가 틀림(1-4 다시), `429`/`insufficient_quota` = 크레딧 부족(1-1의 Billing에서 충전) |
| 지표에 "데이터 준비 중" | 야후 금융/업비트가 잠깐 응답하지 않은 것. 다음 날 보통 자동으로 돌아옵니다 |
| 어떤 섹션이 통째로 없음 | 그 섹션의 소스가 모두 실패했거나 최근 24시간 기사가 없는 날. 로그의 `[섹션이름]` 줄 확인 |
| 아침에 새 호가 안 올라옴 | Actions 탭에서 그날 실행이 있는지 확인. 없으면 **Run workflow** 로 수동 발행. GitHub가 가끔 예약 실행을 건너뜁니다 (그래서 예비 실행이 있습니다) |
| Actions가 빨간 ❌ (배포 단계) | 1-5의 Pages Source가 **GitHub Actions** 인지 확인 |
| OOTD가 사진 대신 일러스트로 나옴 | 로그의 `착샷` 줄 확인. `CLOUDFLARE_... 이 없음` = 1-7의 Secrets 미등록, `응답 401/403` = 토큰이 틀림(다시 발급), `응답 429` = 무료 한도 초과(다음 날 복구) |
| 이메일이 안 옴 | 로그의 `이메일` 줄 확인. `Username and Password not accepted` = 앱 비밀번호 다시 발급 |

> GitHub는 저장소에 60일 동안 아무 변화가 없으면 예약 실행을 멈추는데,
> 이 프로젝트는 매일 발행 데이터를 저장(commit)하므로 계속 살아 있습니다.

---

## 7. 내 컴퓨터에서 실행해 보기

꼭 필요하진 않지만, 디자인을 고치거나 소스를 시험할 때 편합니다.

1. https://www.python.org/downloads/ 에서 **Python 3.11 이상** 설치 (첫 화면의 **Add python.exe to PATH** 체크!)
2. 이 폴더에서 터미널(PowerShell)을 엽니다. (탐색기 주소창에 `powershell` 입력 후 Enter)
3. 라이브러리 설치 (처음 한 번):
   ```bash
   pip install -r requirements.txt
   ```
4. 실행:
   ```bash
   python run.py --no-ai
   ```
   AI와 착샷까지 써 보려면 키를 **그 터미널 창에서만** 임시로 넣고 실행합니다 (파일에 저장하지 않음):
   ```bash
   $env:OPENAI_API_KEY="sk-여기에키"; $env:CLOUDFLARE_ACCOUNT_ID="계정ID"; $env:CLOUDFLARE_API_TOKEN="토큰"; python run.py --no-email
   ```
5. 결과 보기:
   ```bash
   python -m http.server 8000 --directory site
   ```
   브라우저에서 http://localhost:8000 을 엽니다. (끝내려면 터미널에서 Ctrl+C)

| 명령 | 하는 일 |
|---|---|
| `python run.py` | 전체 발행 (수집 → 지표 → AI 편집 → 저장 → 웹페이지 → 이메일) |
| `python run.py --no-ai` | AI 없이 원문 헤드라인으로 |
| `python run.py --no-email` | 이메일은 보내지 않기 |
| `python run.py --render-only` | 수집 없이, 저장된 데이터로 웹페이지만 다시 그리기 (디자인 수정 확인용) |

---

## 8. 어떻게 동작하나요?

```
매일 06:40 GitHub Actions 실행
  │
  ├─ 1. 뉴스 수집 (haru/collect.py)
  │     · 구글 트렌드 인기 검색어 10개 + 검색어별 관련 기사 → 커버스토리 후보
  │     · sources.yaml 의 섹션별 RSS·검색어를 동시에 읽고 최근 24시간 기사만
  │     · 제목이 비슷한 기사(같은 사건)는 하나로 묶고, 여러 매체가 보도한 사건을 위로
  │     · 한 소스가 후보를 독차지하지 않게 고르게 섞어 섹션마다 후보 25개
  │
  ├─ 2. 지표·날씨 (haru/indicators.py, haru/weather.py)
  │     · 코스피(^KS11)·원/달러(KRW=X): 야후 금융 / 비트코인: 업비트 공개 시세
  │     · 오늘 날씨(최고·최저기온, 강수확률): Open-Meteo 무료 API (키 필요 없음)
  │
  ├─ 3. AI 편집 (haru/editor.py → haru/ai_client.py, 기본 Pollinations 무료)
  │     · 커버스토리 3개: 트렌드 중 같은 주제는 합치고 서로 다른 이슈 3개
  │     · 섹션마다 화제성·중요도 높은 1~2개를 고르고 헤드라인·요약을 새로 작성
  │     · AI는 '후보 번호'만 고르고, 매체명·링크는 수집 데이터에서 그대로 → 링크를 지어낼 수 없음
  │     · 검증: 길이, 원문 제목과 똑같은지, 원문 문장을 18자 이상 그대로 베꼈는지
  │       → 위반이면 이유를 알려주고 한 번 더 → 그래도 안 되면 그 섹션만 원문 헤드라인
  │     · AI 서버 자체가 안 되면(키 오류·잔액 부족) 즉시 전체를 원문 헤드라인으로
  │     · 띠별 운세도 AI가, 명언은 quotes.yaml 에서 (출처를 지어내지 않도록)
  │     · 오늘의 OOTD (haru/ootd.py): 날씨 + 오늘의 패션 기사를 보고 여성·남성 한 벌씩 추천
  │       → 페이지에선 사진 대신 직접 그린 옷 실루엣에 추천 색을 입혀 '플랫레이'로
  │       → AI가 안 되는 날은 기온대별 기본 코디 8벌 중 하나 (비 오면 우산 추가)
  │     · 착샷 (haru/lookbook.py): 추천 코디를 영어 프롬프트로 바꿔 FLUX로 생성 (Cloudflare → Hugging Face 순서)
  │       → 얼굴 검출로 턱 아래만 남기고 4:5로 잘라 data/looks/날짜-women.jpg, -men.jpg 로 저장
  │       → 실패한 쪽은 일러스트로 대체
  │
  ├─ 4. data/YYYY-MM-DD.json 저장  ← 모든 결과물의 원본 데이터
  │
  ├─ 5. 웹페이지 (haru/render.py + templates/)
  │     · data/ 의 모든 호를 템플릿에 넣어 site/ 에 다시 그림
  │       site/index.html (최신호), site/archive/날짜.html, site/archive/index.html
  │
  ├─ 5-1. 카드뉴스 (haru/cards.py + templates/cards.html)
  │     · 같은 JSON을 카드 HTML로 그리고 헤드리스 브라우저로 찍어 site/cards/ 에 저장
  │
  ├─ 6. (선택) 이메일 (haru/mailer.py)
  │
  └─ data/*.json 을 저장소에 commit → site/ 를 GitHub Pages에 배포
```

### 폴더 구조
```
├── run.py               실행 파일
├── config.yaml          기본 설정
├── sources.yaml         뉴스 소스 목록
├── quotes.yaml          명언 목록
├── requirements.txt     필요한 파이썬 라이브러리
├── haru/                프로그램 본체
├── templates/           디자인 (HTML·CSS·아이콘, cards.html = 카드뉴스, static/ = 홈 화면 아이콘)
├── tools/make_icons.py  홈 화면 아이콘을 다시 만들 때만 실행
├── .github/workflows/   자동 실행 설정
├── data/                날짜별 호 데이터 + looks/ 착샷 (자동 생성·저장소에 쌓임)
├── site/                완성된 웹페이지 (자동 생성·저장소에는 안 올라감)
└── logs/                실행 기록 (자동 생성·저장소에는 안 올라감)
```

### 데이터 형식 (카드뉴스 등 재활용용)

`data/2026-10-13.json` (웹에서는 `https://.../data/2026-10-13.json`, 최신호는 `.../data/latest.json`)

```jsonc
{
  "schema_version": 1,
  "title": "하루 한 장",
  "date": "2026-10-13", "weekday": "화요일", "vol": 1,
  "generated_at": "2026-10-13T06:41:12+09:00",
  "edit_mode": "ai",              // ai | partial(일부 섹션만 AI) | fallback(원문 헤드라인)
  "reading_minutes": 3,
  "indicators": [
    { "id": "kospi", "name": "코스피", "ok": true, "value": 6384.24, "change": -241.69,
      "change_pct": -3.65, "direction": "down", "display": "6,384.24", "change_display": "▼ 3.65%" }
  ],
  "cover_stories": [
    { "kicker": "가을야구", "headline": "...", "summary": "...", "source": "연합뉴스",
      "link": "https://...", "original_title": "원문 제목" }
  ],
  "sections": [
    { "id": "fashion", "name": "패션",
      "items": [ { "headline": "...", "summary": "...", "source": "...", "link": "...",
                   "original_title": "...", "coverage": 5 } ] }
  ],
  "quote":   { "text": "...", "author": "세네카", "work": "인생의 짧음에 관하여" },
  "weather": { "city": "서울", "t_min": 17, "t_max": 25, "rain_pct": 74, "sky": "이슬비", "display": "..." },
  "ootd": { "by": "ai", "default": "women",      // by: ai | rule(기본 코디)
            "trend": { "title": "참고한 패션 기사", "source": "...", "link": "..." },
            "looks": [
              { "id": "women", "label": "여성", "title": "비 오는 날의 트렌치", "keyword": "레이니 클래식", "tip": "...",
                "items": [ { "category": "outer", "name": "샌드 트렌치코트", "color": "샌드", "hex": "#C9B08A",
                             "en": "sand beige trench coat" } ],
                "photo": "looks/2026-10-13-women.jpg", "photo_prompt": "Fashion photo cropped at the neck ..." },
              { "id": "men", "label": "남성", "...": "같은 형식" } ] },
  "fortune": { "type": "zodiac", "items": [ { "animal": "쥐", "text": "..." } ] }
}
```

카드뉴스(haru/cards.py)도 이 JSON 하나로 만듭니다. 다른 결과물(뉴스레터, 쇼츠 대본 등)을 추가할 때도
수집·편집을 다시 할 필요 없이 이 JSON만 읽으면 됩니다.

### 다른 AI로 바꾸기
`haru/ai_client.py` 에 `complete_json(system, user) → dict` 함수를 가진 클래스를 하나 더 만들고,
`make_client()` 에서 `config.yaml` 의 `ai.provider` 값에 따라 골라 주면 됩니다. 다른 파일은 고칠 필요 없습니다.

### 저작권 원칙
- 언론사 사진·기사 본문은 페이지에 싣지 않습니다. RSS 요약문은 AI가 맥락을 파악하는 데만 쓰고 표시하지 않습니다.
- 헤드라인·요약은 AI가 새로 쓰며, 원문 문장을 베끼면 검증에서 걸러집니다.
- 모든 기사에 출처 매체명과 원문 링크를 붙입니다.
- 비주얼은 타이포그래피, 색 블록, 직접 그린 SVG 아이콘만 씁니다.
