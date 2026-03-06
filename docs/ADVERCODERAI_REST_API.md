# Advercoder AI - Premium API Documentation

## 목차

1. [인증 (Authentication)](#1-인증-authentication)
2. [Rate Limiting](#2-rate-limiting)
3. [공통 응답 형식](#3-공통-응답-형식)
4. [API Key 검증](#4-api-key-검증)
5. [캠페인 API](#5-캠페인-api)
   - [5-1. 캠페인 목록 조회](#5-1-캠페인-목록-조회)
   - [5-2. 캠페인 생성](#5-2-캠페인-생성)
   - [5-3. 캠페인 상세 조회](#5-3-캠페인-상세-조회)
   - [5-4. 캠페인 삭제](#5-4-캠페인-삭제)
   - [5-5. 캠페인 상태 변경](#5-5-캠페인-상태-변경-활성취소)
6. [캠페인 타입별 상세](#6-캠페인-타입별-상세)
   - [6-1. INFO (정보성)](#6-1-info-정보성-포스팅)
   - [6-2. CRAW (크롤링)](#6-2-craw-크롤링-포스팅)
   - [6-3. PARS (크롤링 에이전트)](#6-3-pars-크롤링-에이전트--parsing-agent)
   - [6-4. NSC (네이버 쇼핑 커넥트)](#6-4-nsc-네이버-쇼핑-커넥트)
7. [포스트 API](#7-포스트-api)
   - [7-1. 캠페인별 포스트 조회](#7-1-캠페인별-포스트-조회)
   - [7-2. 전체 포스트 목록 조회](#7-2-전체-포스트-목록-조회)
   - [7-3. 포스트 상세 조회](#7-3-포스트-상세-조회)
   - [7-4. 포스트 수정](#7-4-포스트-수정)
   - [7-5. 포스트 재시도](#7-5-포스트-재시도)
8. [네이버 블로그 (nblog) API](#8-네이버-블로그-nblog-api)
9. [네이버 카페 (naver_cafe) API](#9-네이버-카페-naver_cafe-api)
10. [저장된 프롬프트 API](#10-저장된-프롬프트-api)
11. [열거형 (Enum) 값 레퍼런스](#11-열거형-enum-값-레퍼런스)
12. [공통 필드 상세](#12-공통-필드-상세)
13. [전체 사용 흐름 예시](#13-전체-사용-흐름-예시)
14. [에러 코드](#14-에러-코드)

---

## Base URL

```
https://ai.advercoder.com/api/v1
```

---

## 1. 인증 (Authentication)

모든 API 요청에 `Authorization` 헤더를 포함해야 합니다.

```
Authorization: Bearer pak_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### API Key 발급 방법

1. [ai.advercoder.com](https://ai.advercoder.com)에서 프리미엄 구독
2. 마이페이지 > API 키 관리에서 발급

### 인증 에러

| 상황 | HTTP 코드 | 응답 |
|------|-----------|------|
| 헤더 없음 | 403 | `{"detail": "자격 인증 데이터가 제공되지 않았습니다."}` |
| 잘못된 키 | 401 | `{"detail": "유효하지 않거나 비활성화된 API 키입니다."}` |
| 프리미엄 만료 | 401 | `{"detail": "프리미엄 구독이 만료되었습니다. 구독을 갱신해주세요."}` |

---

## 2. Rate Limiting

API Key 인증 요청에만 적용됩니다. (세션 인증에는 미적용)

| 종류 | 제한 | 설명 |
|------|------|------|
| Burst | 60/min | 순간 폭주 방지 |
| Read (GET) | 500/hour | 읽기 요청 제한 |
| Write (POST/PUT/DELETE) | 300/hour | 쓰기 요청 제한 |

### 제한 초과 시 응답 (429)

```json
{
  "error": "rate_limit_exceeded",
  "detail": "요청 횟수가 제한을 초과했습니다. 45초 후에 다시 시도해주세요.",
  "retry_after": 45
}
```

---

## 3. 공통 응답 형식

### 페이지네이션 (목록 조회)

```json
{
  "count": 100,
  "next": "https://ai.advercoder.com/api/v1/campaigns/?page=2",
  "previous": null,
  "results": [...]
}
```

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `page` | 페이지 번호 | 1 |
| `page_size` | 페이지당 항목 수 | 12 |

---

## 4. API Key 검증

### `GET /premium-auth/verify/`

API Key 상태를 확인합니다.

**요청**

```bash
curl -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/premium-auth/verify/
```

**응답 (200)**

```json
{
  "valid": true,
  "user_id": 1,
  "username": "adver",
  "premium_days_remaining": 613,
  "usage_count": 4,
  "created_at": "2025-06-06T18:06:38.878370",
  "last_used_at": "2026-02-12T01:28:12.592549"
}
```

---

## 5. 캠페인 API

### 캠페인 타입 비교

| 타입 | 코드 | 입력 | 포스트 생성 | 파이프라인 |
|------|------|------|-------------|-----------|
| 정보성 | `INFO` | `titles` (제목///키워드) | 줄 1개 = 포스트 1개 | LLM 직접 생성 |
| 크롤링 | `CRAW` | `titles` (URL///키워드) | 줄 1개 = 포스트 1개 | Selenium 크롤링 → LLM 리라이팅 |
| 크롤링에이전트 | `PARS` | `titles` + `prompts` | 줄 1개 = 포스트 1개 | LangGraph ReAct (researcher→editor) |
| 네이버쇼핑커넥트 | `NSC` | `products` 배열 | 원소 1개 = 포스트 1개 | LangGraph 6단계 |

### 타입별 필드 사용 요약

캠페인 생성 시 각 필드가 실제로 동작하는 타입을 정리한 표입니다. `-`는 값을 보내도 무시됩니다.

| 필드 | INFO | CRAW | PARS | NSC | 비고 |
|------|:----:|:----:|:----:|:---:|------|
| `titles` | O | O | O | `""` 필수 | NSC는 빈 문자열 |
| `products` | - | - | - | O | NSC 전용 |
| `prompts` | - | - | O | - | PARS 전용 (researcher+editor) |
| `tone` | O | O | - | - | 어투 설정 |
| `language` | O | O | - | - | 언어 설정 |
| `additional_prompt` | O | O | - | O | PARS 무시. NSC는 requirement로 전달 |
| `affiliate_link` | 저장만 | O | 저장만 | - | CRAW만 실제 렌더링 |
| `insertion_rules` | O | O | O | - | HTML 삽입 규칙 |
| `image_provider` | O | O | O | - | NSC는 자체 Gemini Imagen |
| `image_size` | O | O | O | - | |
| `image_mode` | O | O | O | - | |
| `image_count` | O | O | O | - | NSC는 products[].image_count |
| `max_section_images` | O | O | O | - | |
| `image_additional_prompt` | O | O | O | - | |
| `image_prompt_mode` | O | O | O | - | |
| `num_products` | O | O | O | O | 쿠팡 상품 개수 |

### 포스트 생성 방식

캠페인을 생성(`POST /campaigns/`)하면 포스트가 **순차적으로 비동기 생성**됩니다.

- `titles`의 줄 수(또는 `products` 배열 원소 수)만큼 포스트가 자동 생성됨
- 각 포스트는 `start_date`부터 `publish_interval` 간격으로 `publish_date`가 설정됨
- LLM 글 작성은 `publish_date` 순서대로 순차 실행됨 (동시 실행 아님)
- 캠페인 생성 API 응답은 즉시 반환되며, 포스트 작성은 백그라운드에서 진행됨
- 포스트 작성 완료 여부는 `GET /campaigns/{id}/posts/?status=COM`으로 폴링하여 확인

### 비용

| 타입 | 포스트당 | 이미지당 |
|------|----------|----------|
| INFO | 1코인 | +1코인 |
| CRAW | 1코인 | +1코인 |
| PARS | 5코인 | +1코인 |
| NSC | 5코인 | +1코인 |

---

### 5-1. 캠페인 목록 조회

#### `GET /campaigns/`

**쿼리 파라미터**

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `search` | 캠페인명/제목/유형 검색 | `?search=커피` |
| `page` | 페이지 번호 | `?page=2` |
| `page_size` | 페이지 크기 (최대 100) | `?page_size=20` |

**요청**

```bash
curl -H "Authorization: Bearer pak_xxx" \
  "https://ai.advercoder.com/api/v1/campaigns/?search=테스트&page_size=5"
```

**응답 (200)**

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 879,
      "user": 1,
      "campaign_name": "API Key 테스트 캠페인",
      "type": "INFO",
      "titles": "커피 원두 종류별 특징과 맛 비교",
      "affiliate_link": "",
      "status": "ACT",
      "publish_category_id": null,
      "created_date": "2026-02-12T01:29:01.789612",
      "updated_date": "2026-02-12T01:29:01.789926",
      "start_date": "2026-02-12T10:00:00",
      "publish_interval": 0,
      "publish_status": "DNP",
      "image_size": "NOIMG",
      "num_products": 4,
      "tistory_blog": null,
      "tistory_blog_name": null,
      "blogspot_blog": null,
      "blogspot_blog_name": null,
      "nblog": null,
      "nblog_name": null,
      "tone": "FRD",
      "model_choice": "GEMINI20FLASH",
      "language": "KO",
      "total_posts": 1,
      "completed_posts": 0,
      "prompts": {},
      "insertion_rules": {},
      "additional_prompt": null,
      "original_images": [],
      "image_count": 6,
      "shoping_link": null,
      "image_provider": "NOIMG",
      "image_mode": "THUMB",
      "max_section_images": 4,
      "image_additional_prompt": null,
      "image_prompt_mode": "SIMPLE"
    }
  ]
}
```

---

### 5-2. 캠페인 생성

#### `POST /campaigns/`

**요청 바디**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `campaign_name` | string | O | 캠페인 이름 |
| `type` | string | O | 캠페인 유형 (아래 표 참조) |
| `titles` | string | O | 제목 목록 (줄바꿈으로 구분, 여러 개 가능) |
| `model_choice` | string | O | LLM 모델 (아래 표 참조) |
| `start_date` | datetime | O | 작성 시작 시간 (ISO 8601) |
| `publish_status` | string | O | 발행 상태 |
| `publish_interval` | int | O | 발행 간격 (분 단위, 0=즉시) |
| `selected_blog` | int | - | 발행할 블로그 ID (`publish_status`가 `DNP`가 아닌 경우 필수, 아래 참조) |
| `tone` | string | - | 어투 (기본: `FRD`) — INFO/CRAW만 |
| `language` | string | - | 언어 (기본: `KO`) — INFO/CRAW만 |
| `image_size` | string | - | 이미지 크기 (기본: `NOIMG`) — INFO/CRAW/PARS |
| `image_provider` | string | - | 이미지 생성 제공자 (기본: `NOIMG`) — INFO/CRAW/PARS |
| `image_mode` | string | - | 이미지 모드 (기본: `THUMB`) — INFO/CRAW/PARS |
| `image_count` | int | - | 이미지 개수 0~10 (기본: 6) — INFO/CRAW/PARS |
| `max_section_images` | int | - | 소제목별 최대 이미지 1~10 (기본: 4) — INFO/CRAW/PARS |
| `image_additional_prompt` | string | - | 이미지 추가 프롬프트 — INFO/CRAW/PARS |
| `image_prompt_mode` | string | - | 이미지 프롬프트 방식 (기본: `SIMPLE`) — INFO/CRAW/PARS |
| `additional_prompt` | string | - | 추가 프롬프트 (최대 2000자) — INFO/CRAW(`{keyword}` 치환), NSC(`requirement`로 전달) |
| `affiliate_link` | string | - | 어필리에이트 링크 — CRAW만 실제 렌더링 |
| `num_products` | int | - | 쿠팡 상품 개수 3~10 (기본: 4) |
| `prompts` | object | - | PARS 타입 전용 에이전트 프롬프트 |
| `insertion_rules` | object | - | HTML 삽입 규칙 |
| `products` | array | - | NSC 타입 전용 제품 배열 |

**응답 (201 Created)**

캠페인 목록 조회(`GET /campaigns/`)의 `results[]` 항목과 동일한 구조입니다. `id` 필드로 생성된 캠페인을 식별합니다.

---

### 5-3. 캠페인 상세 조회

#### `GET /campaigns/{id}/`

```bash
curl -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/campaigns/880/
```

---

### 5-4. 캠페인 삭제

#### `DELETE /campaigns/{id}/`

```bash
curl -X DELETE \
  -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/campaigns/880/
```

**응답**: `204 No Content`

---

### 5-5. 캠페인 상태 변경 (활성/취소)

#### `POST /campaigns/{id}/update_status/`

| 파라미터 | 값 | 결과 |
|----------|-----|------|
| `active` | `true` | 캠페인 상태 → `ACT` (활성) |
| `active` | `false` | 캠페인 상태 → `CAN` (취소) |

```bash
# 캠페인 취소
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{"active": false}' \
  https://ai.advercoder.com/api/v1/campaigns/880/update_status/

# 캠페인 재활성화
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{"active": true}' \
  https://ai.advercoder.com/api/v1/campaigns/880/update_status/
```

**응답 (200)**

```json
{"status": "success"}
```

- `COM`(완료)은 모든 포스트 처리 완료 시 자동 전환됨

---

## 6. 캠페인 타입별 상세

### 6-1. INFO (정보성 포스팅)

#### titles 형식

```
제목1///키워드1
제목2///키워드2
제목만 (키워드 없이도 가능)
```

- `///` 구분자: 왼쪽=제목, 오른쪽=키워드(최대 10자)
- 키워드 없으면 전체가 제목
- 줄바꿈(`\n`)으로 여러 포스트 구분
- 줄 1개 = 포스트 1개

#### titles 파싱 로직

```python
raw = "커피 원두 종류별 특징///커피원두"
if "///" in raw:
    title = "커피 원두 종류별 특징"      # 왼쪽
    main_keyword = "커피원두"             # 오른쪽 (최대 10자)
else:
    title = raw.strip()
    main_keyword = None
```

#### 파이프라인

```
제목+키워드 입력
  → LLM이 원문 콘텐츠 생성 (Markdown)
  → HTML 변환 + 보강
  → insertion_rules 적용
  → 이미지 생성 (선택)
  → 발행
```

#### Post 필드 매핑

| Post 필드 | 값 | 설명 |
|-----------|-----|------|
| `title` | `///` 왼쪽 | 포스트 제목 |
| `main_keyword` | `///` 오른쪽 (10자) | 메인 키워드 |
| `affiliate_link` | 캠페인 값 복사 | 글 말미 삽입 |
| `craw_url` | NULL | 미사용 |

#### 요청 예시 (최소)

```bash
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "커피 블로그",
    "type": "INFO",
    "titles": "커피 원두 종류별 특징///커피원두\n아메리카노와 라떼 차이점///커피종류",
    "model_choice": "GEMINI30FLASH",
    "start_date": "2026-02-12T23:00:00",
    "publish_status": "DNP",
    "publish_interval": 60
  }' \
  https://ai.advercoder.com/api/v1/campaigns/
```

#### 요청 예시 (전체 옵션)

```bash
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "커피 블로그",
    "type": "INFO",
    "titles": "커피 원두 종류별 특징///커피원두\n아메리카노와 라떼 차이점///커피종류\n핸드드립 입문 가이드",
    "model_choice": "GEMINI30PRO",
    "tone": "FRD",
    "language": "KO",
    "start_date": "2026-02-12T23:00:00",
    "publish_status": "NBL",
    "selected_blog": 119,
    "publish_interval": 60,
    "affiliate_link": "https://link.coupang.com/xxx",
    "additional_prompt": "{keyword}에 대해 전문적으로 설명해주세요. 초보자도 이해할 수 있도록 작성해주세요.",
    "insertion_rules": {
      "before_h2_1": "<div class=\"ad-banner\">광고 배너 HTML</div>",
      "document_end": "<p>이 포스팅은 쿠팡 파트너스 활동의 일환입니다.</p>"
    },
    "image_provider": "GEMINI",
    "image_count": 6,
    "image_size": "1024x1024",
    "image_mode": "FULL",
    "image_prompt_mode": "LLM",
    "image_additional_prompt": "밝고 따뜻한 카페 분위기로",
    "max_section_images": 3
  }' \
  https://ai.advercoder.com/api/v1/campaigns/
```

#### {keyword} 치환 동작

`additional_prompt` 내 `{keyword}`는 각 포스트의 `main_keyword`로 치환됩니다:

```
additional_prompt: "{keyword}에 대해 전문적으로 설명해주세요"

포스트1 (main_keyword: "커피원두"):
  → "커피원두에 대해 전문적으로 설명해주세요"

포스트2 (main_keyword: "커피종류"):
  → "커피종류에 대해 전문적으로 설명해주세요"
```

---

### 6-2. CRAW (크롤링 포스팅)

#### titles 형식

```
https://example.com/article-1///키워드1
@https://example.com/article-2///키워드2
https://example.com/article-3
```

- `@` 접두사: 선택 (자동 제거됨)
- URL이 `title`과 `craw_url` 양쪽에 저장됨
- 키워드는 선택 (최대 10자)

#### titles 파싱 로직

```python
raw = "@https://example.com/article///키워드"
if raw.startswith("@"):
    raw = raw[1:].strip()  # "@" 제거 → "https://example.com/article///키워드"

if "///" in raw:
    url = "https://example.com/article"  # 왼쪽 → title + craw_url
    main_keyword = "키워드"               # 오른쪽 (최대 10자)
else:
    url = raw
    main_keyword = None
```

#### 파이프라인

```
URL 입력
  → Selenium 헤드리스 크롤링 (최대 10,000자)
  → 최소 500자 필요 (미만 시 CER 상태)
  → LLM이 새 제목 생성 (URL → 실제 제목으로 교체)
  → LLM이 콘텐츠 리라이팅 (Markdown)
  → HTML 변환
  → insertion_rules 적용 ({post_url} → 원본 URL로 치환)
  → 이미지 생성 (선택)
  → 발행
```

#### 크롤링 상세

- Selenium + headless Chrome
- User-Agent 랜덤화
- 30초 타임아웃, 최대 3회 재시도
- nav, sidebar, footer, ads, comments 등 자동 제거
- 최소 500자 미만 → `CER` (크롤링 에러) 상태

#### Post 필드 매핑

| Post 필드 | 값 | 설명 |
|-----------|-----|------|
| `title` | URL (초기) → LLM 생성 제목 (완료 후) | 크롤링 후 교체됨 |
| `craw_url` | URL | 크롤링 대상 URL |
| `main_keyword` | `///` 오른쪽 (10자) | 메인 키워드 |
| `affiliate_link` | 캠페인 값 복사 | 글 말미 삽입 |

#### 요청 예시 (최소)

```bash
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "크롤링 블로그",
    "type": "CRAW",
    "titles": "https://blog.example.com/best-laptop-2026\nhttps://blog.example.com/coffee-guide",
    "model_choice": "GEMINI30FLASH",
    "start_date": "2026-02-12T23:00:00",
    "publish_status": "DNP",
    "publish_interval": 60
  }' \
  https://ai.advercoder.com/api/v1/campaigns/
```

#### 요청 예시 (전체 옵션)

```bash
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "크롤링 블로그",
    "type": "CRAW",
    "titles": "https://blog.example.com/best-laptop-2026///노트북\n@https://blog.example.com/coffee-guide///커피\nhttps://blog.example.com/phone-review",
    "model_choice": "GEMINI30FLASH",
    "tone": "PRF",
    "language": "KO",
    "start_date": "2026-02-12T23:00:00",
    "publish_status": "NBL",
    "selected_blog": 119,
    "publish_interval": 60,
    "additional_prompt": "원문의 핵심을 유지하면서 {keyword} 관점으로 재구성해주세요.",
    "insertion_rules": {
      "before_h2_1": "<p class=\"source\">원문 출처: <a href=\"{post_url}\">{post_url}</a></p>",
      "document_end": "<p>이 글은 <a href=\"{post_url}\">원문</a>을 기반으로 작성되었습니다.</p>"
    },
    "image_provider": "GEMINI",
    "image_count": 3,
    "image_size": "1024x1024",
    "image_mode": "THUMB"
  }' \
  https://ai.advercoder.com/api/v1/campaigns/
```

#### {post_url} 치환 동작

`insertion_rules` 내 `{post_url}`은 각 포스트의 `craw_url`로 치환됩니다:

```
insertion_rules.document_end: "출처: <a href=\"{post_url}\">{post_url}</a>"

포스트1 (craw_url: "https://blog.example.com/best-laptop-2026"):
  → "출처: <a href=\"https://blog.example.com/best-laptop-2026\">https://blog.example.com/best-laptop-2026</a>"
```

#### 특이사항

- 크롤링 실패 시 `CER` 상태 (다른 타입의 `ERR`과 구분)
- `title`은 초기에 URL이 저장되고, 크롤링+LLM 완료 후 실제 제목으로 교체됨

---

### 6-3. PARS (크롤링 에이전트 / Parsing Agent)

#### titles 형식

INFO와 동일:
```
주제1///키워드1
주제2///키워드2
```

#### prompts 필드 (필수)

PARS 타입은 반드시 `prompts` 필드가 필요합니다. `researcher`와 `editor` 두 에이전트를 정의해야 합니다.

```json
{
  "researcher": {
    "role": "역할 설명 (필수, 문자열)",
    "goal": "목표 설명 (필수, 문자열)",
    "backstory": "배경 설명 (필수, 문자열)"
  },
  "editor": {
    "role": "역할 설명 (필수, 문자열)",
    "goal": "목표 설명 (필수, 문자열)",
    "backstory": "배경 설명 (필수, 문자열)"
  }
}
```

**기본 프롬프트 (Default):**

`role`과 `goal`은 아래 기본값을 그대로 사용하세요. 수정하지 않는 것을 권장합니다. **`backstory`만 용도에 맞게 수정**하세요.

```json
{
  "researcher": {
    "role": "온라인 자료 검색 및 정보 분석",
    "goal": "정확하고 신뢰할 수 있는 정보 제공",
    "backstory": "당신은 정확하고 신뢰할 수 있는 정보를 제공하는 것을 최우선으로 여깁니다. 다양한 출처를 통해 정보를 수집하고, 항상 사실 확인을 철저히 하여 최신의 정확한 정보만을 제공합니다. url의 끝이 pdf로 끝나는 url은 정보수집에서 제외해 주세요! 팀원들과의 협력을 중요시하며, 귀하의 전문성으로 프로젝트에 기여하고자 합니다."
  },
  "editor": {
    "role": "독자 친화적이고 정보가 풍부한 한국어 콘텐츠 작성",
    "goal": "추출된 데이터를 정제하고 구조화하여 고품질 데이터셋 생성",
    "backstory": "당신은 독자들이 쉽게 이해하고 공감할 수 있는 콘텐츠를 만듭니다. 정보 전달과 함께 독자의 관심을 끌 수 있는 글쓰기에 능숙합니다. 주요 포털 사이트와 SNS에서 잘 노출될 수 있는 콘텐츠 최적화 능력이 있습니다. 검색 최적화(SEO)를 고려하여 적절한 키워드를 자연스럽게 사용해 주세요. 블로그 포스트는 2000자 이상으로 작성하며, 필요시 마크다운 형식의 링크나 표를 포함해 주세요. 한국인들이 사용하지 않는 단어와 표현을 사용하지 마세요 (영어식 표현.). 이 프로젝트의 중요성을 잘 알고 있으며, 최선을 다해 임하고 있습니다."
  }
}
```

> **Tip:** `backstory`에 `{keyword}`를 넣으면 각 포스트의 main_keyword로 자동 치환됩니다.

**검증 규칙:**
- `researcher`, `editor` 키 모두 필수
- 각 에이전트에 `role`, `goal`, `backstory` 필드 모두 필수
- 모든 필드는 문자열이어야 함
- `{keyword}` 사용 가능 (main_keyword로 치환)

#### 파이프라인 (LangGraph)

```
주제+키워드 입력
  → research 노드 (ReAct 에이전트)
    - 도구: search_google, search_naver_local, search_naver_blog,
            scrape_naver_blog, scrape_website
    - researcher의 role/goal/backstory 기반 행동
  → editor 노드 (LLM)
    - editor의 role/goal/backstory 기반 글 작성
    - Markdown 출력
  → HTML 변환
  → H1 태그 제거 (제목으로 사용)
  → insertion_rules 적용
  → 이미지 생성 (선택)
  → 발행
```

#### Post 필드 매핑

| Post 필드 | 값 | 설명 |
|-----------|-----|------|
| `title` | `///` 왼쪽 | 포스트 제목 |
| `main_keyword` | `///` 오른쪽 (10자) | 메인 키워드 |
| `affiliate_link` | 캠페인 값 복사 | 글 말미 삽입 |
| `craw_url` | NULL | 미사용 |

- `prompts`는 Campaign에만 저장 (Post에는 저장 안함)

#### 요청 예시 (최소)

```bash
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "AI 리서치 블로그",
    "type": "PARS",
    "titles": "2026년 최고의 노트북 추천///노트북추천",
    "prompts": {
      "researcher": {
        "role": "IT 제품 전문 리서처",
        "goal": "최신 노트북 스펙, 가격, 리뷰를 수집하여 정리합니다",
        "backstory": "10년간 IT 미디어에서 제품 리뷰를 담당한 전문가"
      },
      "editor": {
        "role": "블로그 콘텐츠 에디터",
        "goal": "리서치 결과를 SEO 최적화된 블로그 포스트로 작성합니다",
        "backstory": "네이버 인플루언서 출신으로 월 100만 PV 블로그 운영 경험"
      }
    },
    "model_choice": "GEMINI30PRO",
    "start_date": "2026-02-12T23:00:00",
    "publish_status": "DNP",
    "publish_interval": 120
  }' \
  https://ai.advercoder.com/api/v1/campaigns/
```

#### 요청 예시 (전체 옵션, {keyword} 활용)

```bash
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "AI 리서치 블로그",
    "type": "PARS",
    "titles": "2026년 최고의 노트북 추천///노트북추천\n맥북 vs 갤럭시북 비교///맥북비교",
    "prompts": {
      "researcher": {
        "role": "{keyword} 분야 전문 리서처",
        "goal": "{keyword}의 최신 정보, 스펙, 가격, 실사용 리뷰를 수집하여 정리합니다",
        "backstory": "10년간 IT 미디어에서 {keyword} 관련 제품 리뷰를 담당한 전문가로, 신뢰할 수 있는 소스에서 정확한 정보를 찾는 능력이 뛰어남"
      },
      "editor": {
        "role": "{keyword}에 관한 블로그 콘텐츠 에디터",
        "goal": "리서치 결과를 토대로 {keyword}에 대한 SEO 최적화된 고품질 블로그 포스트를 작성합니다",
        "backstory": "네이버 인플루언서 출신으로 월 100만 PV 블로그 운영 경험. 복잡한 IT 제품 정보를 쉽고 재미있게 전달하는데 전문성 보유"
      }
    },
    "model_choice": "GEMINI30PRO",
    "tone": "EXP",
    "language": "KO",
    "start_date": "2026-02-12T23:00:00",
    "publish_status": "NBL",
    "selected_blog": 119,
    "publish_interval": 120,
    "image_provider": "GEMINI",
    "image_count": 4,
    "image_size": "1024x1024",
    "image_mode": "FULL"
  }' \
  https://ai.advercoder.com/api/v1/campaigns/
```

#### prompts 검증 실패 시 에러

```json
// researcher 누락
{"prompts": ["크롤링 에이전트 유형에는 'researcher' 에이전트가 필요합니다."]}

// role 필드 누락
{"prompts": ["'researcher'의 'role' 필드가 필요합니다."]}

// 문자열이 아닌 값
{"prompts": ["'role'는 문자열이어야 합니다."]}
```

#### 특이사항

- 포스트당 5코인 소모 (INFO/CRAW는 1코인)
- researcher가 실제 웹 검색 수행 (Google, 네이버)
- editor가 검색 결과 기반으로 글 작성
- 가장 고품질이지만 가장 느림

---

### 6-4. NSC (네이버 쇼핑 커넥트)

**주의: `titles`가 아닌 `products` 배열을 사용합니다!** `titles`는 빈 문자열(`""`)로 보내야 합니다.

#### products 배열 구조

```json
"products": [
  {
    "title": "제품명 (필수)",
    "shoping_link": "https://naver.me/xxx (선택)",
    "original_images": ["이미지URL1", "이미지URL2"] ,
    "image_count": 6
  }
]
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `title` | string | O | 제품명 |
| `shoping_link` | string | - | 네이버 쇼핑 링크 (오타 아님, 백엔드 필드명) |
| `original_images` | array | - | AI 이미지 생성의 원본 이미지 URL (기본: []) |
| `image_count` | int | - | 제품당 이미지 생성 수 0~10 (기본: 0) |

- 원소 1개 = 포스트 1개
- 첫 번째 제품의 `shoping_link`, `original_images`, `image_count`가 Campaign 모델에도 복사됨
- `products` 배열은 write-only (응답에 미포함)

#### 파이프라인 (LangGraph 6단계)

```
제품 정보 입력
  → title_generation (블로그 제목 생성)
  → research (네이버 블로그 유사글 검색)
  → content_planning (글 구조 기획)
  → image_planning (이미지 배치 계획)
  → image_generation (Gemini Imagen → Cloudflare R2)
  → content_writing (Gemini 2.5 Pro, 20,000 토큰)
  → HTML 변환 + 발행
```

#### Post 필드 매핑

| Post 필드 | 값 | 설명 |
|-----------|-----|------|
| `title` | products[].title | 제품명 → LLM이 블로그 제목으로 교체 |
| `product_title` | products[].title | 원본 제품명 보존 |
| `shopping_link` | products[].shoping_link | 쇼핑 링크 |
| `original_images` | products[].original_images | 원본 이미지 |
| `image_count` | products[].image_count | 이미지 생성 수 |
| `main_keyword` | NULL | NSC는 main_keyword 없음 |

#### 이미지 생성 (INFO/CRAW/PARS와 다름!)

NSC의 이미지 생성은 캠페인 레벨 `image_provider`/`image_size`/`image_mode` 등을 **사용하지 않습니다.**

| 항목 | INFO/CRAW/PARS | NSC |
|------|---------------|-----|
| 생성 엔진 | `image_provider`로 선택 (GEMINI/OPENAI) | **항상 Gemini Imagen** |
| 이미지 소스 | 글 내용 기반 프롬프트로 생성 | `original_images`(제품 사진)를 **참고하여 변형** |
| 이미지 수 | 캠페인 `image_count` | `products[].image_count` (제품별) |
| 배치 방식 | `image_mode` (THUMB/FULL) | image_planning 노드가 글 구조 보고 자동 계획 |
| 저장 | HTML에 직접 삽입 | **Cloudflare R2 업로드** → URL로 삽입 |
| 크기/프롬프트 | `image_size`, `image_prompt_mode` 등 사용 | 무관 (자체 프롬프트 생성) |

- `original_images`가 비어있으면 텍스트 프롬프트만으로 생성
- `image_count`가 0이면 이미지 생성 건너뜀

#### 검증

- `image_count > 0` → 프리미엄 필수 + Gemini API 키 필수 (connected=True)
- 이미지 검증은 제품별로 수행

#### 이미지 검증 실패 시 에러

```json
{"image_count": ["이미지 생성 기능은 프리미엄 전용입니다."]}
{"image_count": ["Gemini API 키를 연결해주세요."]}
```

#### 요청 예시 (최소)

```bash
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "생활용품 리뷰",
    "type": "NSC",
    "titles": "",
    "products": [
      {
        "title": "다이슨 V15 무선청소기",
        "shoping_link": "https://naver.me/G5k5U86z"
      }
    ],
    "model_choice": "GEMINI30PRO",
    "start_date": "2026-02-12T23:05:00",
    "publish_status": "DNP",
    "publish_interval": 60
  }' \
  https://ai.advercoder.com/api/v1/campaigns/
```

#### 요청 예시 (전체 옵션, 다중 제품 + 이미지)

```bash
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "생활용품 리뷰",
    "type": "NSC",
    "titles": "",
    "products": [
      {
        "title": "다이슨 V15 무선청소기",
        "shoping_link": "https://naver.me/G5k5U86z",
        "original_images": [
          "https://shopping-phinf.pstatic.net/main_123/img1.jpg",
          "https://shopping-phinf.pstatic.net/main_123/img2.jpg"
        ],
        "image_count": 6
      },
      {
        "title": "삼성 비스포크 공기청정기",
        "shoping_link": "https://naver.me/ABC123",
        "original_images": ["https://shopping-phinf.pstatic.net/main_456/img1.jpg"],
        "image_count": 4
      },
      {
        "title": "LG 퓨리케어 정수기",
        "shoping_link": "https://naver.me/XYZ789",
        "original_images": [],
        "image_count": 0
      }
    ],
    "selected_blog": 119,
    "start_date": "2026-02-12T23:05:00",
    "publish_status": "NBL",
    "publish_interval": 60,
    "model_choice": "GEMINI30PRO",
    "additional_prompt": "실사용 후기 느낌으로 작성해주세요."
  }' \
  https://ai.advercoder.com/api/v1/campaigns/
```

#### 비용

- 포스트당 5코인 + 이미지 성공당 1코인

---

## 7. 포스트 API

### 7-1. 캠페인별 포스트 조회

#### `GET /campaigns/{id}/posts/`

특정 캠페인에 속한 포스트 목록을 조회합니다.

**쿼리 파라미터**

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `search` | 제목/내용 검색 | `?search=커피` |
| `status` | 상태 필터 | `?status=COM` |
| `ordering` | 정렬 (기본: `-created_date`) | `?ordering=publish_date` |
| `page` | 페이지 번호 | `?page=2` |

```bash
curl -H "Authorization: Bearer pak_xxx" \
  "https://ai.advercoder.com/api/v1/campaigns/880/posts/?status=COM"
```

**응답 (200)**

```json
{
  "count": 18,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 12345,
      "title": "포스트 제목",
      "status": "COM",
      "publish_date": "2026-03-05T18:10:00",
      "created_date": "2026-03-04T16:00:00",
      "error_message": null
    }
  ]
}
```

---

### 7-2. 전체 포스트 목록 조회

#### `GET /posts/`

모든 캠페인의 포스트를 조회합니다.

**쿼리 파라미터**

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `status` | 상태 필터 | `?status=COM` |
| `blog` | 워드프레스 블로그 FK | `?blog=1` |
| `campaigns` | 캠페인 ID | `?campaigns=120905` |
| `campaigns__nblog` | 네이버 블로그 ID | `?campaigns__nblog=650` |
| `search` | 제목/본문 검색 | `?search=가습기` |
| `ordering` | 정렬 | `?ordering=-publish_date` |
| `page` | 페이지 번호 | `?page=2` |
| `page_size` | 페이지 크기 (최대 100) | `?page_size=50` |

```bash
curl -H "Authorization: Bearer pak_xxx" \
  "https://ai.advercoder.com/api/v1/posts/?status=COM&page_size=20"
```

---

### 7-3. 포스트 상세 조회

#### `GET /posts/{id}/`

```bash
curl -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/posts/1234/
```

**응답 (200)**

```json
{
  "id": 12345,
  "title": "포스트 제목",
  "status": "COM",
  "publish_date": "2026-03-05T18:10:00",
  "created_date": "2026-03-04T16:00:00",
  "post_context": "<h2>소제목</h2><p>본문 HTML...</p>",
  "affiliate_link": "https://naver.me/xxx",
  "main_keyword": "키워드",
  "error_message": null
}
```

---

### 7-4. 포스트 수정

#### `PATCH /posts/{id}/`

```bash
curl -X PATCH \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{"publish_date": "2026-02-20T17:00:00"}' \
  https://ai.advercoder.com/api/v1/posts/1234/
```

- 포스트의 개별 필드 수정 가능
- 주로 `publish_date` 변경에 사용

---

### 7-5. 포스트 재시도

#### `POST /posts/{id}/retry/`

오류(`ERR`, `CER`) 상태인 포스트를 재시도합니다.

```bash
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/posts/1234/retry/
```

#### `POST /posts/retry_selected/`

여러 포스트를 한번에 재시도합니다.

```bash
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{"post_ids": [1234, 1235, 1236]}' \
  https://ai.advercoder.com/api/v1/posts/retry_selected/
```

---

## 8. 네이버 블로그 (nblog) API

### 발행 방식 안내

네이버 블로그/티스토리/블로그스팟 발행은 **워드프레스와 다르게 동작합니다.**

| 플랫폼 | 발행 방식 |
|--------|----------|
| **워드프레스** (`PUB`) | 포스트 작성 완료 시 **자동 발행** (API로 직접 발행) |
| **네이버 블로그** (`NBL`) | 포스트 작성 완료 → `pending` 상태로 **발행 대기** → 외부 프로그램으로 발행 |
| **네이버 카페** (`NCF`) | 동일 (외부 프로그램 필요, cafe_id + menu_id로 게시판 지정) |
| **티스토리** (`TIS`) | 동일 (외부 프로그램 필요) |
| **블로그스팟** (`BSP`) | 동일 (외부 프로그램 필요) |

**네이버 블로그 발행 전체 흐름:**

```
1. 캠페인 생성 (publish_status: "NBL", selected_blog: 119)
   → 포스트 생성 + LLM 글 작성
   → 완료 시 nblog 포스트가 "pending" 상태로 생성됨

2. 발행 대기 포스트 조회
   GET /nblog/posts/{api_key}/  (pending만 반환)
   또는
   GET /nblog/blogs/{blog_id}/posts/  (pending + published)

3. 외부 프로그램이 실제 네이버 블로그에 글 발행
   - Selenium/Playwright 등으로 네이버 블로그에 로그인 후 글 작성
   - 또는 별도 발행 도구 사용
   - Advercoder는 발행 기능을 제공하지 않음, 직접 구현 필요

4. 발행 완료 후 상태 업데이트
   POST /nblog/posts/update-status/
   (post_id=nblog_id, post_url=발행된URL)
```

---

### 8-1. 블로그 목록 조회

#### `GET /nblog/blogs/`

```bash
curl -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/nblog/blogs/
```

---

### 8-2. 블로그별 포스트 조회

#### `GET /nblog/blogs/{blog_id}/posts/`

```bash
curl -H "Authorization: Bearer pak_xxx" \
  "https://ai.advercoder.com/api/v1/nblog/blogs/119/posts/?page=1"
```

- `blog_id`: 블로그 ID
- 페이지네이션: `?page=1` (page_size=10 고정)
- **실제 발행 여부 확인은 이 API로** (포스트 API의 COM/PUB 상태와 다름)

**응답 (200)**

```json
{
  "count": 35,
  "next": "...?page=2",
  "results": [
    {
      "id": 88411,
      "status": "pending",
      "url": null,
      "post": {
        "id": 12345,
        "title": "포스트 제목",
        "post_context": "<h2>소제목</h2><p>본문...</p>",
        "publish_date": "2026-03-05T18:10:00"
      }
    }
  ]
}
```

- `id` = nblog_id (발행 상태 업데이트 시 사용)
- `post.id` = post_id (publish_date PATCH 시 사용)
- `status`: `pending` / `published`
- `url`: 발행 후 블로그 URL, pending이면 null

---

### 8-3. 발행용 포스트 조회

#### `GET /nblog/posts/{api_key}/`

- `{api_key}`: Premium API Key (`pak_xxx` 형식, Bearer 토큰과 동일한 키)
- 인증 헤더 불필요 (URL에 키가 포함되어 있으므로)
- **pending 상태만** 반환 (발행 대상)
- publish_date 오래된 순서대로
- 외부 발행 프로그램이 이 엔드포인트를 폴링하여 발행할 포스트를 가져감

---

### 8-4. nblog 포스트 상태 변경

#### `PATCH /nblog/posts/{post_id}/status/`

```bash
curl -X PATCH \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{"status": "pending"}' \
  https://ai.advercoder.com/api/v1/nblog/posts/88411/status/
```

- `post_id`: nblog 포스트 ID (응답의 `id` 필드)
- 유효 값: `pending`, `published`, `failed`
- `pending`으로 변경 시 `url` 필드도 자동 초기화
- 용도: 발행 실패 후 재발행, 발행 취소 등

---

### 8-5. 발행 완료 상태 업데이트

#### `POST /nblog/posts/update-status/`

발행기(publisher)가 발행 완료 후 호출합니다.

```bash
curl -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "post_id=88411&post_url=https://blog.naver.com/xxx/123" \
  https://ai.advercoder.com/api/v1/nblog/posts/update-status/
```

- `post_id`에 nblog_id를 전송 (post_id 아님!)
- 인증 불필요

---

## 9. 네이버 카페 (naver_cafe) API

### 발행 방식 안내

네이버 카페 발행은 네이버 블로그와 동일한 **외부 프로그램 발행** 방식입니다.

**네이버 카페 = 카페 + 게시판 조합**

같은 카페의 다른 게시판은 별도 항목으로 등록합니다. (예: "맛집카페 - 자유게시판", "맛집카페 - 맛집후기")

**네이버 카페 발행 전체 흐름:**

```
1. 캠페인 생성 (publish_status: "NCF", selected_blog: 카페ID)
   → 포스트 생성 + LLM 글 작성
   → 완료 시 naver_cafe 포스트가 "pending" 상태로 생성됨

2. 발행 대기 포스트 조회
   GET /naver_cafe/posts/{api_key}/  (pending만 반환)

3. 외부 프로그램이 실제 네이버 카페에 글 발행
   - cafe_id와 menu_id로 글쓰기 페이지 접근
   - 글쓰기 URL: cafe.naver.com/ca-fe/cafes/{cafeId}/menus/{menuId}/articles/write

4. 발행 완료 후 상태 업데이트
   POST /naver_cafe/posts/update-status/
```

---

### 9-1. 카페 목록 조회

#### `GET /naver_cafe/cafes/`

```bash
curl -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/naver_cafe/cafes/
```

**응답 (200)**

```json
[
  {
    "id": 1,
    "name": "맛집카페 - 자유게시판",
    "cafe_id": "31083775",
    "menu_id": "2",
    "api_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "created_at": "2026-03-05T10:00:00",
    "updated_at": "2026-03-05T10:00:00"
  }
]
```

---

### 9-2. 카페 등록

#### `POST /naver_cafe/cafes/`

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | O | 표시 이름 (예: "맛집카페 - 자유게시판") |
| `cafe_id` | string | O | 카페 숫자 ID (URL의 `/cafes/31083775/` 부분) |
| `menu_id` | string | O | 게시판 메뉴 ID (숫자) |

```bash
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "맛집카페 - 자유게시판",
    "cafe_id": "31083775",
    "menu_id": "2"
  }' \
  https://ai.advercoder.com/api/v1/naver_cafe/cafes/
```

---

### 9-3. 카페 수정/삭제

#### `PUT /naver_cafe/cafes/{cafe_id}/`
#### `DELETE /naver_cafe/cafes/{cafe_id}/`

```bash
# 수정
curl -X PUT \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{"name": "맛집카페 - 맛집후기", "cafe_id": "31083775", "menu_id": "3"}' \
  https://ai.advercoder.com/api/v1/naver_cafe/cafes/1/

# 삭제
curl -X DELETE \
  -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/naver_cafe/cafes/1/
```

---

### 9-4. 카페별 포스트 조회

#### `GET /naver_cafe/cafes/{cafe_id}/posts/`

```bash
curl -H "Authorization: Bearer pak_xxx" \
  "https://ai.advercoder.com/api/v1/naver_cafe/cafes/1/posts/?page=1"
```

**응답 (200)**

```json
{
  "count": 10,
  "next": "...?page=2",
  "results": [
    {
      "id": 100,
      "status": "pending",
      "url": "",
      "cafe_name": "맛집카페 - 자유게시판",
      "cafe_id_str": "mycafe123",
      "menu_id": "2",
      "cafe_pk": 1,
      "post": {
        "id": 12345,
        "title": "포스트 제목",
        "post_context": "<h2>소제목</h2><p>본문...</p>",
        "publish_date": "2026-03-05T18:10:00"
      }
    }
  ]
}
```

---

### 9-5. 발행용 포스트 조회

#### `GET /naver_cafe/posts/{api_key}/`

- pending 상태만 반환
- 인증 헤더 불필요 (URL에 키 포함)
- 발행 프로그램이 폴링하는 엔드포인트

---

### 9-6. 발행 완료 상태 업데이트

#### `POST /naver_cafe/posts/update-status/`

```bash
curl -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "post_id=100&post_url=https://cafe.naver.com/mycafe123/12345" \
  https://ai.advercoder.com/api/v1/naver_cafe/posts/update-status/
```

- `post_id`에 naver_cafe 포스트 ID를 전송
- 인증 불필요

---

### 9-7. 카페 포스트 상태 변경

#### `PATCH /naver_cafe/posts/{post_id}/status/`

```bash
curl -X PATCH \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{"status": "pending"}' \
  https://ai.advercoder.com/api/v1/naver_cafe/posts/100/status/
```

- 유효 값: `pending`, `published`, `failed`
- `pending`으로 변경 시 `url` 자동 초기화

---

## 10. 저장된 프롬프트 API

### `GET /content-prompts/`

```bash
curl -H "Authorization: Bearer pak_xxx" \
  "https://ai.advercoder.com/api/v1/content-prompts/?prompt_type=NSC_PROMPT"
```

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `prompt_type` | 타입 필터 | `?prompt_type=NSC_PROMPT` |

- 유효 타입: `NSC_PROMPT`, `INFO_PROMPT`, `CRAW_PROMPT`
- 파라미터 없으면 전체 반환

**응답 (200)**

```json
[
  {
    "id": 924,
    "name": "프롬프트1",
    "prompt_type": "NSC_PROMPT",
    "content": "프롬프트 본문..."
  }
]
```

#### 활용 방법

API에서는 프롬프트 `name`을 직접 지정하는 필드가 없습니다.
프롬프트를 활용하려면 조회한 `content` 값을 캠페인 생성 시 `additional_prompt` 필드에 직접 넣어야 합니다.

```bash
# 1. 프롬프트 조회
curl -H "Authorization: Bearer pak_xxx" \
  "https://ai.advercoder.com/api/v1/content-prompts/?prompt_type=INFO_PROMPT"
# => [{"id": 924, "name": "인컴5", "content": "프롬프트 본문..."}]

# 2. content를 additional_prompt에 넣어서 캠페인 생성
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "테스트",
    "type": "INFO",
    "titles": "제목///키워드",
    "additional_prompt": "프롬프트 본문...",
    ...
  }' \
  https://ai.advercoder.com/api/v1/campaigns/
```

---

## 11. 열거형 (Enum) 값 레퍼런스

### 캠페인 유형 (`type`)

| 값 | 설명 |
|----|------|
| `INFO` | 정보성 포스팅 |
| `CRAW` | 크롤링 포스팅 |
| `CRA3` | Claude3 크롤링 포스팅 (Beta) |
| `COP1` | 쿠팡 파트너스 키워드 기반 |
| `COP2` | 쿠팡 파트너스 단일 제품 |
| `PARS` | Parsing Agent |
| `NSC` | 네이버 쇼핑 커넥트 |

### LLM 모델 (`model_choice`)

| 값 | 설명 | API 키 필요 |
|----|------|-------------|
| `GEMINI20FLASH` | Gemini 2.0 Flash | Gemini |
| `GEMINI20FLASHLITE` | Gemini 2.0 Flash Lite | Gemini |
| `GEMINI25FLASH` | Gemini 2.5 Flash | Gemini |
| `GEMINI25FLASHLITE` | Gemini 2.5 Flash Lite | Gemini |
| `GEMINI25PRO` | Gemini 2.5 Pro | Gemini |
| `GEMINI30FLASH` | Gemini 3.0 Flash | Gemini |
| `GEMINI30PRO` | Gemini 3.0 Pro (3/9 중단 예정) | Gemini |
| `GEMINI31PRO` | Gemini 3.1 Pro | Gemini |
| `GEMINI31FLITE` | Gemini 3.1 Flash Lite | Gemini |
| `GEMINI` | Gemini (레거시) | Gemini |
| `GPT35` | GPT Turbo 3.5 | OpenAI |
| `GPT-4` | GPT-4 | OpenAI |
| `GPT-4o` | GPT-4o | OpenAI |
| `GPT-4o-Mini` | GPT-4o-Mini | OpenAI |
| `o3-mini` | o3-mini | OpenAI |
| `GPT-5` | GPT-5 | OpenAI |
| `GPT-5-Mini` | GPT-5-Mini | OpenAI |
| `CL3H` | Claude3 Haiku | Claude |
| `CL35H` | Claude3.5 Haiku | Claude |
| `CL3S` | Claude3.5 Sonnet | Claude |
| `CL37S` | Claude3.7 Sonnet | Claude |
| `CL4S` | Claude Sonnet 4 | Claude |
| `CL45S` | Claude Sonnet 4.5 | Claude |
| `CL45H` | Claude Haiku 4.5 | Claude |

### 어투 (`tone`)

**INFO, CRAW 타입에서만 사용됩니다.** PARS, NSC에서는 무시됩니다.

| 값 | 설명 |
|----|------|
| `FRD` | 친근한 |
| `PRF` | 전문적인 |
| `CNV` | 대화형 |
| `HMR` | 유머러스한 |
| `EMP` | 공감 |
| `EDU` | 교육적인 |
| `CRT` | 창의적인 |
| `ANG` | 화난 |
| `EXP` | 경험담 |

### 언어 (`language`)

**INFO, CRAW 타입에서만 사용됩니다.** PARS, NSC에서는 무시됩니다.

| 값 | 설명 |
|----|------|
| `KO` | 한국어 |
| `EN` | 영어 |
| `JA` | 일본어 |

### 발행 상태 (`publish_status`)

| 값 | 설명 | selected_blog 필수 | selected_blog 대상 |
|----|------|-------------------|--------------------|
| `DNP` | 발행안함 (콘텐츠만 생성) | X | - |
| `NBL` | 네이버 블로그 발행 | O | NblogBlog ID (`GET /nblog/blogs/`로 조회) |
| `NCF` | 네이버 카페 발행 | O | NaverCafe ID (`GET /naver_cafe/cafes/`로 조회) |
| `TIS` | 티스토리 발행 | O | TistoryBlog ID |
| `BSP` | 블로그스팟 발행 | O | BlogspotBlog ID |
| `PUB` | 워드프레스 발행 | O | Blog(워드프레스) ID |

`selected_blog`는 `publish_status`에 따라 다른 모델의 ID를 가리킵니다. 블로그 목록은 각 플랫폼별 API로 조회합니다.

### 캠페인 상태 (`status`)

| 값 | 설명 |
|----|------|
| `ACT` | 활성 |
| `COM` | 완료 |
| `CAN` | 취소 |

### 포스트 상태 (`status`)

| 값 | 설명 |
|----|------|
| `SCH` | 예약됨 |
| `WRI` | 작성중 |
| `COM` | 작성완료 |
| `PUB` | 발행완료 |
| `CAN` | 취소됨 |
| `ERR` | 오류 |
| `CER` | 크롤링 실패 (CRAW 전용) |

### 이미지 관련 필드

**INFO, CRAW, PARS 타입에서 사용됩니다.** NSC는 `products[].image_count`와 `products[].original_images`로 별도 관리됩니다.

#### 이미지 크기 (`image_size`)

| 값 | 설명 |
|----|------|
| `NOIMG` | 이미지 사용안함 |
| `1024x1024` | 1024x1024 |
| `1792x1024` | 1792x1024 |
| `1024x1792` | 1024x1792 |

#### 이미지 제공자 (`image_provider`)

| 값 | 설명 |
|----|------|
| `NOIMG` | 이미지 사용안함 |
| `OPENAI` | OpenAI DALL-E 3 |
| `GEMINI` | Gemini Flash Image |

#### 이미지 모드 (`image_mode`)

| 값 | 설명 |
|----|------|
| `THUMB` | 대표이미지만 |
| `FULL` | 대표이미지 + 소제목별 이미지 |

#### 이미지 프롬프트 방식 (`image_prompt_mode`)

| 값 | 설명 |
|----|------|
| `SIMPLE` | 간단 프롬프트 (직접 구성) |
| `LLM` | LLM으로 프롬프트 생성 |

---

## 12. 공통 필드 상세

### additional_prompt

- **INFO, CRAW, NSC 타입에서 사용됩니다.** PARS에서는 무시됩니다.
- 최대 2000자
- INFO/CRAW: `{keyword}` → `main_keyword`로 치환됨
- NSC: `requirement`(글 작성 요구사항)로 전달됨

### insertion_rules

**INFO, CRAW, PARS 타입에서 사용됩니다.** NSC에서는 무시됩니다.

생성된 HTML 콘텐츠의 특정 위치에 커스텀 HTML을 삽입합니다. 값은 HTML 문자열입니다.

#### 사용 가능한 키

| 키 | 설명 |
|----|------|
| `before_h2_1` | 첫 번째 H2 태그 **앞**에 삽입 |
| `before_h2_2` | 두 번째 H2 태그 **앞**에 삽입 |
| `before_h2_N` | N번째 H2 태그 **앞**에 삽입 |
| `after_h2_1` | 첫 번째 H2 태그 **뒤**에 삽입 |
| `after_h2_2` | 두 번째 H2 태그 **뒤**에 삽입 |
| `after_h2_N` | N번째 H2 태그 **뒤**에 삽입 |
| `document_end` | 문서 맨 끝에 삽입 |

- `N`은 1부터 시작하는 H2 태그 순번 (글에 H2가 5개면 1~5까지 사용 가능)
- 존재하지 않는 H2 번호를 지정하면 무시됨
- 각 삽입 위치에 자동으로 `&nbsp;` 공백 문단이 추가됨
- CRAW 타입에서는 값 내 `{post_url}` → 원본 크롤링 URL로 치환

#### 예시: 2번째 H2 뒤에 광고 삽입 + 문서 끝에 출처

```json
{
  "after_h2_2": "<div class=\"ad-box\"><a href=\"https://link.coupang.com/xxx\"><img src=\"배너URL\"></a><p>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 지급받습니다.</p></div>",
  "document_end": "<p>더 많은 정보는 <a href=\"https://example.com\">여기</a>에서 확인하세요.</p>"
}
```

#### 결과 HTML 구조

```html
<h2>첫 번째 소제목</h2>
<p>첫 번째 섹션 내용...</p>

<h2>두 번째 소제목</h2>
<!-- ↓ after_h2_2 삽입 위치 -->
<p>&nbsp;</p>
<div class="ad-box">...</div>
<p>&nbsp;</p>
<!-- ↑ after_h2_2 삽입 완료 -->
<p>두 번째 섹션 내용...</p>

<h2>세 번째 소제목</h2>
<p>세 번째 섹션 내용...</p>

<!-- ↓ document_end 삽입 위치 -->
<p>&nbsp;</p>
<p>더 많은 정보는...</p>
```

#### 예시: 1번째 H2 앞에 목차 + 3번째 H2 뒤에 CTA

```json
{
  "before_h2_1": "<div class=\"toc\"><p><strong>목차</strong></p><ul><li>소제목1</li><li>소제목2</li></ul></div>",
  "after_h2_3": "<p class=\"cta\">지금 바로 <a href=\"https://example.com\">신청하세요!</a></p>"
}
```

---

## 13. 전체 사용 흐름 예시

```bash
# 1. API Key 검증
curl -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/premium-auth/verify/

# 2. 정보성 캠페인 생성 (제목 3개)
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "맛집 블로그",
    "type": "INFO",
    "titles": "서울 강남 맛집 베스트 10///강남맛집\n홍대 카페 추천///홍대카페\n이태원 브런치 맛집///이태원맛집",
    "model_choice": "GEMINI25FLASH",
    "start_date": "2026-02-12T10:00:00",
    "publish_status": "DNP",
    "publish_interval": 60,
    "tone": "FRD",
    "language": "KO"
  }' \
  https://ai.advercoder.com/api/v1/campaigns/
# => {"id": 881, "total_posts": 3, ...}

# 3. 포스트 작성 완료 대기 후 조회
curl -H "Authorization: Bearer pak_xxx" \
  "https://ai.advercoder.com/api/v1/campaigns/881/posts/?status=COM"

# 4. 특정 포스트 상세 조회 (HTML 본문 포함)
curl -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/posts/1234/

# 5. 오류 포스트 재시도
curl -X POST \
  -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/posts/1235/retry/

# 6. 캠페인 삭제
curl -X DELETE \
  -H "Authorization: Bearer pak_xxx" \
  https://ai.advercoder.com/api/v1/campaigns/881/
```

---

## 14. 에러 코드

| HTTP 코드 | 설명 |
|-----------|------|
| 200 | 성공 |
| 201 | 생성 성공 |
| 204 | 삭제 성공 (본문 없음) |
| 400 | 잘못된 요청 (필수 필드 누락, 유효하지 않은 값) |
| 401 | 인증 실패 (잘못된 API Key, 프리미엄 만료) |
| 403 | 권한 없음 (구독 필요, 다른 유저의 리소스) |
| 404 | 리소스 없음 |
| 429 | Rate Limit 초과 |
| 500 | 서버 에러 |
