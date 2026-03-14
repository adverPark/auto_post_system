"""네이버 카페 자동 발행 스크립트 (Playwright)

Usage:
    # 기본 발행 (모든 pending 즉시 발행)
    uv run python scripts/publish_cafe.py --preset 대표프리셋

    # 스케줄 발행 (publish_date 기준 예약 발행, 완료 시 자동 종료)
    uv run python scripts/publish_cafe.py --preset 대표프리셋 --schedule

    # 에디터 테스트 (Phase B)
    uv run python scripts/publish_cafe.py --preset 대표프리셋 --test-html test.html

    # 헤드리스 (안정화 후)
    uv run python scripts/publish_cafe.py --preset 대표프리셋 --headless

    # 포스트간 딜레이 조정
    uv run python scripts/publish_cafe.py --preset 대표프리셋 --delay 10

    # 드라이런 (로그인 + API 조회만)
    uv run python scripts/publish_cafe.py --preset 대표프리셋 --dry-run
"""

import argparse
import asyncio
import hashlib
import json
import os
import signal
import shutil
import sys
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup, NavigableString
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

BASE_URL = "https://ai.advercoder.com/api/v1"
API_KEY = os.getenv("ADVERCODER_API_KEY")
PRESETS_PATH = os.path.join(os.path.dirname(__file__), "..", "configs", "presets.json")
CONFIGS_DIR = os.path.join(os.path.dirname(__file__), "..", "configs")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots")
TEMP_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "temp_images")
LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
MODIFIER = "Meta" if sys.platform == "darwin" else "Control"
KST = timezone(timedelta(hours=9))


def download_image(url: str) -> str | None:
    """이미지 URL → 임시 파일 다운로드, 경로 반환. 실패 시 None."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        # 확장자 결정
        content_type = r.headers.get("content-type", "")
        if "png" in content_type:
            ext = ".png"
        elif "gif" in content_type:
            ext = ".gif"
        elif "webp" in content_type:
            ext = ".webp"
        else:
            ext = ".jpg"
        os.makedirs(TEMP_IMAGES_DIR, exist_ok=True)
        filename = hashlib.md5(url.encode()).hexdigest() + ext
        filepath = os.path.join(TEMP_IMAGES_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(r.content)
        print(f"  [IMG] 다운로드 완료: {filepath} ({len(r.content)} bytes)")
        return filepath
    except Exception as e:
        print(f"  [IMG-ERROR] 다운로드 실패 ({url}): {e}")
        return None


def cleanup_temp_images():
    """임시 이미지 디렉토리 삭제."""
    if os.path.exists(TEMP_IMAGES_DIR):
        shutil.rmtree(TEMP_IMAGES_DIR)
        print(f"[CLEANUP] temp_images 삭제 완료")


async def screenshot(page, name: str):
    """디버깅용 스크린샷 저장."""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
    await page.screenshot(path=path, full_page=False)
    print(f"  [SCREENSHOT] {path}")

DEFAULT_TEST_HTML = """\
<h2>테스트 대제목 (인용구4 + 24pt)</h2>
<p>첫 번째 문단입니다. <strong>볼드 텍스트</strong> 포함.</p>
<p>두 번째 문단입니다. 문단 사이에 빈 줄이 들어가야 합니다.</p>
<img src="https://picsum.photos/400/300" alt="테스트 이미지">
<h3>부제목 (인용구2 + 19pt)</h3>
<p>부제목 아래 문단입니다.</p>
<ul><li>항목 1</li><li>항목 2</li></ul>
<table><tr><th>헤더1</th><th>헤더2</th></tr><tr><td>값1</td><td>값2</td></tr></table>
"""


# ── PID File (중복 실행 방지) ────────────────────────────


def get_pid_path(preset_name: str) -> str:
    return os.path.join(LOGS_DIR, f"schedule_{preset_name}.pid")


def is_schedule_running(preset_name: str) -> bool:
    """같은 프리셋의 스케줄 프로세스가 이미 실행 중인지 확인."""
    pid_path = get_pid_path(preset_name)
    if not os.path.exists(pid_path):
        return False
    with open(pid_path) as f:
        pid = int(f.read().strip())
    try:
        os.kill(pid, 0)  # 프로세스 존재 확인 (시그널 안 보냄)
        return True
    except (ProcessLookupError, PermissionError, ValueError):
        os.remove(pid_path)  # 죽은 PID 파일 정리
        return False


def write_pid_file(preset_name: str):
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(get_pid_path(preset_name), "w") as f:
        f.write(str(os.getpid()))


def remove_pid_file(preset_name: str):
    pid_path = get_pid_path(preset_name)
    if os.path.exists(pid_path):
        os.remove(pid_path)


# ── Schedule Utils (시간 필터링) ─────────────────────────


def is_publish_time(post: dict) -> bool:
    """post.publish_date가 현재 시각 이전이면 True (발행 시간 도래)."""
    publish_date_str = post.get("post", {}).get("publish_date")
    if not publish_date_str:
        return True  # publish_date 없으면 즉시 발행
    try:
        publish_dt = datetime.fromisoformat(publish_date_str)
        if publish_dt.tzinfo is None:
            publish_dt = publish_dt.replace(tzinfo=KST)
        return datetime.now(KST) >= publish_dt
    except (ValueError, TypeError):
        return True


def get_next_publish_time(posts: list[dict]) -> datetime | None:
    """가장 가까운 미래의 publish_date를 반환. 없으면 None."""
    next_time = None
    for post in posts:
        publish_date_str = post.get("post", {}).get("publish_date")
        if not publish_date_str:
            continue
        try:
            publish_dt = datetime.fromisoformat(publish_date_str)
            if publish_dt.tzinfo is None:
                publish_dt = publish_dt.replace(tzinfo=KST)
            if publish_dt > datetime.now(KST):
                if next_time is None or publish_dt < next_time:
                    next_time = publish_dt
        except (ValueError, TypeError):
            continue
    return next_time


# ── API Functions ─────────────────────────────────────────


def api_headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def fetch_cafes() -> list[dict]:
    """카페 목록 조회 (api_key, cafe_id, menu_id 포함)"""
    r = requests.get(f"{BASE_URL}/naver_cafe/cafes/", headers=api_headers())
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("results", [])


def fetch_pending_posts(api_key: str) -> list[dict]:
    """pending 상태 포스트 조회 (인증 불필요)"""
    r = requests.get(f"{BASE_URL}/naver_cafe/posts/{api_key}/")
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return data
    return data.get("results", [])


def update_post_status(post_id: int, post_url: str):
    """발행 완료 상태 업데이트 (form-urlencoded, 인증 불필요)"""
    r = requests.post(
        f"{BASE_URL}/naver_cafe/posts/update-status/",
        data={"post_id": post_id, "post_url": post_url},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    r.raise_for_status()
    return r.json() if r.text else {}


def mark_post_failed(post_id: int):
    """포스트 상태를 failed로 변경 (Bearer 인증)"""
    r = requests.patch(
        f"{BASE_URL}/naver_cafe/posts/{post_id}/status/",
        headers=api_headers(),
        json={"status": "failed"},
    )
    r.raise_for_status()
    return r.json() if r.text else {}


# ── HTML → Editor Actions ────────────────────────────────


INLINE_TAGS = {"strong", "b", "em", "i", "u", "a", "span", "br", "sub", "sup", "code"}
BLOCK_TAGS = {"h2", "h3", "p", "ul", "ol", "table", "div", "blockquote", "hr", "img", "pre"}


def parse_inline_node(node) -> list[dict]:
    """단일 inline 노드를 파싱하여 children 리스트로 반환."""
    if isinstance(node, NavigableString):
        text = str(node)
        if text:
            return [{"type": "text", "text": text}]
        return []

    tag = node.name
    if tag in ("strong", "b"):
        return [{"type": "bold", "text": node.get_text()}]
    elif tag in ("em", "i"):
        return [{"type": "italic", "text": node.get_text()}]
    elif tag == "u":
        return [{"type": "underline", "text": node.get_text()}]
    elif tag == "a":
        href = node.get("href", "")
        text = node.get_text()
        return [{"type": "text", "text": f"{text} ({href})" if href else text}]
    elif tag == "br":
        return [{"type": "text", "text": "\n"}]
    else:
        text = node.get_text()
        if text:
            return [{"type": "text", "text": text}]
        return []


def parse_inline_children(element) -> list[dict]:
    """블록 요소 내부의 inline children을 파싱."""
    children = []
    for child in element.children:
        children.extend(parse_inline_node(child))
    return children


def html_to_editor_actions(html: str) -> list[dict]:
    """HTML을 파싱하여 에디터 액션 리스트로 변환.

    연속된 inline 요소(text, strong, u 등)는 하나의 paragraph로 묶는다.
    블록 요소(h2, h3, p, table 등)는 독립된 액션으로 처리한다.
    """
    soup = BeautifulSoup(html, "html.parser")
    actions = []
    inline_buffer = []  # 연속된 inline 노드를 모아두는 버퍼

    def flush_inline_buffer():
        """버퍼에 모인 inline 노드들을 하나의 paragraph 액션으로 변환."""
        if not inline_buffer:
            return
        children = []
        for node in inline_buffer:
            children.extend(parse_inline_node(node))
        inline_buffer.clear()
        # 첫 번째/마지막 text 노드의 선행/후행 공백 제거
        if children and children[0].get("type") == "text":
            children[0]["text"] = children[0]["text"].lstrip()
        if children and children[-1].get("type") == "text":
            children[-1]["text"] = children[-1]["text"].rstrip()
        # 빈 text 노드 제거
        children = [c for c in children if c.get("text", "").strip() or c["type"] != "text"]
        # 공백만 있는 경우 스킵
        text_only = "".join(c.get("text", "") for c in children).strip()
        if text_only:
            actions.append({"type": "paragraph", "children": children})

    for element in soup.children:
        # NavigableString (텍스트 노드) → inline buffer에 추가
        if isinstance(element, NavigableString):
            text = str(element)
            if text.strip():
                inline_buffer.append(element)
            elif inline_buffer:
                # 공백 텍스트도 inline buffer에 있으면 유지 (단어 간 공백)
                inline_buffer.append(element)
            continue

        tag = element.name
        if tag is None:
            continue

        # inline 태그 → buffer에 추가
        if tag in INLINE_TAGS:
            inline_buffer.append(element)
            continue

        # block 태그 → buffer 먼저 flush 후 처리
        flush_inline_buffer()

        if tag == "p":
            text_content = element.get_text().strip()
            if text_content in ("", "\xa0"):
                actions.append({"type": "empty_line"})
                continue
            children = parse_inline_children(element)
            if children:
                actions.append({"type": "paragraph", "children": children})

        elif tag == "h2":
            children = parse_inline_children(element)
            if not children:
                children = [{"type": "text", "text": element.get_text()}]
            actions.append({"type": "quote_underline", "children": children})

        elif tag == "h3":
            children = parse_inline_children(element)
            if not children:
                children = [{"type": "text", "text": element.get_text()}]
            actions.append({"type": "quote_line", "children": children})

        elif tag in ("ul", "ol"):
            for idx, li in enumerate(element.find_all("li", recursive=False), 1):
                prefix = f"{idx}. " if tag == "ol" else "- "
                li_children = parse_inline_children(li)
                text_children = [{"type": "text", "text": prefix}] + li_children
                actions.append({"type": "list_item", "children": text_children})

        elif tag == "table":
            actions.append({"type": "table_paste", "html": str(element)})

        elif tag == "div":
            inner_actions = html_to_editor_actions(element.decode_contents())
            actions.extend(inner_actions)

        elif tag == "img":
            src = element.get("src", "")
            if src and src.startswith("http"):
                actions.append({"type": "image_upload", "src": src})

        else:
            text = element.get_text().strip()
            if text:
                actions.append({"type": "paragraph", "children": [{"type": "text", "text": text}]})

    # 마지막에 남은 inline buffer flush
    flush_inline_buffer()
    return actions


# ── Editor Execution Engine ──────────────────────────────


async def clipboard_paste(page, text: str):
    """클립보드에 텍스트 쓰고 붙여넣기."""
    await page.evaluate("async (t) => await navigator.clipboard.writeText(t)", text)
    await page.keyboard.press(f"{MODIFIER}+KeyV")


async def type_inline_children(page, children: list[dict]):
    """inline children을 순서대로 에디터에 입력."""
    for child in children:
        if child["type"] == "text":
            text = child["text"]
            if "\n" in text:
                parts = text.split("\n")
                for i, part in enumerate(parts):
                    if part:
                        await page.keyboard.type(part, delay=10)
                    if i < len(parts) - 1:
                        await page.keyboard.press("Enter")
            else:
                await page.keyboard.type(text, delay=10)
        elif child["type"] == "bold":
            await page.keyboard.press(f"{MODIFIER}+KeyB")
            await page.keyboard.type(child["text"], delay=10)
            await page.keyboard.press(f"{MODIFIER}+KeyB")
        elif child["type"] == "italic":
            await page.keyboard.press(f"{MODIFIER}+KeyI")
            await page.keyboard.type(child["text"], delay=10)
            await page.keyboard.press(f"{MODIFIER}+KeyI")
        elif child["type"] == "underline":
            await page.keyboard.press(f"{MODIFIER}+KeyU")
            await page.keyboard.type(child["text"], delay=10)
            await page.keyboard.press(f"{MODIFIER}+KeyU")


async def close_floating_menus(page):
    """SE 에디터의 플로팅 메뉴(글감, 검색 등)를 강제로 닫는다."""
    await page.evaluate("""() => {
        // 모든 플로팅 메뉴/검색 영역 닫기
        document.querySelectorAll(
            '.se-floating-material-menu, .se-floating-search-area, .se-floating-material-container'
        ).forEach(el => {
            el.classList.remove('se-is-expanded');
            el.style.display = 'none';
            el.style.visibility = 'hidden';
            el.style.pointerEvents = 'none';
        });
    }""")
    await page.wait_for_timeout(200)


async def escape_component_block(page):
    """SE 에디터에서 컴포넌트 블록(인용구 등)을 탈출하여 새 텍스트 블록에 커서를 위치시킨다.

    canvas-bottom-button을 JS dispatchEvent로 트리거하여 새 텍스트 컴포넌트를 생성하고,
    해당 paragraph를 클릭하여 커서를 이동시킨다.
    """
    # 1. 플로팅 메뉴 닫기 (canvas-bottom-button을 가릴 수 있음)
    await close_floating_menus(page)

    # 2. canvas-bottom-button을 dispatchEvent로 트리거 → 새 텍스트 컴포넌트 생성
    await page.evaluate("""() => {
        const btn = document.querySelector('button.se-canvas-bottom-button');
        if (btn) {
            btn.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
            btn.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
            btn.dispatchEvent(new MouseEvent('click', {bubbles: true}));
        }
    }""")
    await page.wait_for_timeout(500)

    # 3. 플로팅 메뉴 다시 닫기 (canvas-bottom 클릭으로 열릴 수 있음)
    await close_floating_menus(page)

    # 4. 새로 생성된 텍스트 paragraph에 포커스
    text_paras = page.locator(".se-component.se-text p.se-text-paragraph")
    if await text_paras.count() > 0:
        await text_paras.last.click(force=True)
        await page.wait_for_timeout(300)


async def select_font_size(page, size: int):
    """SE 에디터에서 글씨 크기를 선택한다. (11,13,15,16,19,24,28,30,34,38)"""
    size_btn = page.locator("button.se-font-size-code-toolbar-button")
    await size_btn.click()
    await page.wait_for_timeout(500)
    option_btn = page.locator(f"button.se-toolbar-option-font-size-code-fs{size}-button")
    await option_btn.click()
    await page.wait_for_timeout(300)


async def apply_quote(page, quote_type: str, children: list[dict]):
    """인용구 서식 적용 -> 글씨 크기 설정 -> 텍스트 입력 -> 인용구 블록 탈출.

    quote_type: 'quote_underline' (인용구4, h2용) 또는 'quote_line' (인용구2, h3용)
    """
    # 1. 인용구 드롭다운 열기
    container = page.locator("li.se-toolbar-item-insert-quotation")
    dropdown_btn = container.locator("button.se-document-toolbar-select-option-button")
    await dropdown_btn.click()
    await page.wait_for_timeout(500)

    # 2. 스타일 선택
    quote_button_map = {
        "quote_underline": "button.se-toolbar-option-insert-quotation-quotation_underline-button",
        "quote_line": "button.se-toolbar-option-insert-quotation-quotation_line-button",
        "quote_bubble": "button.se-toolbar-option-insert-quotation-quotation_bubble-button",
    }
    selector = quote_button_map.get(quote_type, quote_button_map["quote_line"])
    await page.locator(selector).click()
    await page.wait_for_timeout(500)

    # 3. 글씨 크기 설정 (인용구 안에서)
    if quote_type == "quote_underline":
        await select_font_size(page, 24)
    elif quote_type == "quote_line":
        await select_font_size(page, 19)

    # 4. inline children 입력
    await type_inline_children(page, children)

    # 5. 인용구 블록 탈출
    await escape_component_block(page)


async def paste_table_html(page, table_html: str):
    """테이블 HTML을 clipboard text/html로 복사 후 에디터에 paste."""
    await page.evaluate(
        """async (html) => {
        const blob = new Blob([html], {type: 'text/html'});
        await navigator.clipboard.write([new ClipboardItem({'text/html': blob})]);
    }""",
        table_html,
    )
    await page.keyboard.press(f"{MODIFIER}+KeyV")
    await page.wait_for_timeout(500)


async def upload_image_to_editor(page, image_path: str):
    """SE 에디터에 이미지를 업로드한다.

    방법 A: 사진 버튼 클릭 → file_chooser로 파일 선택
    방법 B (대안): 숨겨진 input[type=file]에 직접 set_input_files()
    """
    abs_path = os.path.abspath(image_path)

    # 방법 A: 사진 버튼 클릭 → file chooser
    try:
        image_btn = page.locator("li.se-toolbar-item-image button.se-document-toolbar-basic-button")
        if await image_btn.count() > 0:
            async with page.expect_file_chooser(timeout=5000) as fc_info:
                await image_btn.first.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(abs_path)
            await page.wait_for_timeout(3000)
            await screenshot(page, "img_upload_a")
            # 이미지 컴포넌트 탈출
            await escape_component_block(page)
            print(f"  [IMG] 업로드 완료 (방법 A): {image_path}")
            return
    except Exception as e:
        print(f"  [IMG] 방법 A 실패: {e}, 방법 B 시도...")

    # 방법 B: 숨겨진 input[type=file] 직접 조작
    try:
        # SE 에디터의 숨겨진 file input 찾기
        file_input = page.locator("input[type='file'][accept*='image']")
        if await file_input.count() == 0:
            # 사진 버튼을 먼저 클릭하여 input을 생성
            image_btn = page.locator("li.se-toolbar-item-image button")
            if await image_btn.count() > 0:
                await image_btn.first.click()
                await page.wait_for_timeout(1000)
            file_input = page.locator("input[type='file'][accept*='image']")

        if await file_input.count() > 0:
            await file_input.first.set_input_files(abs_path)
            await page.wait_for_timeout(3000)
            await screenshot(page, "img_upload_b")
            await escape_component_block(page)
            print(f"  [IMG] 업로드 완료 (방법 B): {image_path}")
            return
    except Exception as e:
        print(f"  [IMG] 방법 B도 실패: {e}")

    print(f"  [IMG-WARN] 이미지 업로드 스킵: {image_path}")


async def execute_editor_actions(page, actions: list[dict]):
    """액션 리스트를 순서대로 에디터에 반영."""
    for idx, action in enumerate(actions):
        action_type = action["type"]

        if action_type in ("quote_underline", "quote_bubble", "quote_line"):
            await apply_quote(page, action_type, action["children"])
        elif action_type == "paragraph":
            await type_inline_children(page, action["children"])
            await page.keyboard.press("Enter")
            # p와 p 사이 빈 줄 추가 (다음 액션이 paragraph인 경우)
            if idx + 1 < len(actions) and actions[idx + 1]["type"] == "paragraph":
                await page.keyboard.press("Enter")
        elif action_type == "list_item":
            await type_inline_children(page, action["children"])
            await page.keyboard.press("Enter")
        elif action_type == "table_paste":
            await paste_table_html(page, action["html"])
        elif action_type == "image_upload":
            try:
                image_path = download_image(action["src"])
                if image_path:
                    await upload_image_to_editor(page, image_path)
                else:
                    print(f"  [IMG-SKIP] 다운로드 실패 → 스킵")
            except Exception as e:
                print(f"  [IMG-ERROR] 이미지 업로드 실패 → 스킵: {e}")
        elif action_type == "empty_line":
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(200)


# ── Login ────────────────────────────────────────────────


async def naver_login(page, naver_id: str, naver_pw: str):
    """네이버 로그인 (clipboard paste 방식, 봇 감지 우회)."""
    await page.goto("https://nid.naver.com/nidlogin.login")
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(1000)
    await screenshot(page, "01_login_page")

    # ID 입력 (clipboard paste)
    id_input = page.locator("#id")
    await id_input.click()
    await clipboard_paste(page, naver_id)
    await page.wait_for_timeout(500)

    # PW 입력 (clipboard paste)
    pw_input = page.locator("#pw")
    await pw_input.click()
    await clipboard_paste(page, naver_pw)
    await page.wait_for_timeout(500)
    await screenshot(page, "02_credentials_filled")

    # 로그인 버튼 클릭
    await page.locator("#log\\.login").click()
    await page.wait_for_timeout(3000)
    await screenshot(page, "03_after_login_click")

    # 로그인 후 중간 페이지 처리 (기기 등록, 보안 확인 등)
    for attempt in range(30):
        url = page.url
        print(f"  [LOGIN] URL: {url}")

        # 기기 등록 페이지 → "등록 안 함" 클릭
        if "device" in url or "new_device" in url:
            await screenshot(page, f"04_device_page_{attempt}")
            skip_btn = page.locator("a.btn_cancel, button.btn_cancel, #new\\.dontsave, a:has-text('등록 안 함'), button:has-text('등록안함')")
            if await skip_btn.count() > 0:
                print("  [LOGIN] 기기 등록 → '등록 안 함' 클릭")
                await skip_btn.first.click()
                await page.wait_for_timeout(2000)
                continue

        # 보안 설정 등 다른 중간 페이지
        if "nid.naver.com" in url and "nidlogin.login" not in url:
            await screenshot(page, f"04_intermediate_{attempt}")
            # "나중에 하기" / "건너뛰기" 버튼 탐색
            later_btn = page.locator("a:has-text('나중에'), button:has-text('나중에'), a:has-text('건너뛰기'), button:has-text('건너뛰기')")
            if await later_btn.count() > 0:
                print("  [LOGIN] 중간 페이지 → '나중에/건너뛰기' 클릭")
                await later_btn.first.click()
                await page.wait_for_timeout(2000)
                continue

        # 로그인 페이지에서 벗어나지 못한 경우
        if "nidlogin.login" in url:
            if attempt < 29:
                await page.wait_for_timeout(2000)
                continue
            await screenshot(page, "05_login_stuck")
            raise RuntimeError("로그인 실패: 로그인 페이지에서 벗어나지 못함")

        # nid.naver.com을 벗어났으면 성공
        if "nid.naver.com" not in url:
            break

        await page.wait_for_timeout(1000)

    await screenshot(page, "06_login_complete")
    print(f"[OK] 로그인 완료 URL: {page.url}")


async def check_login_status(page) -> bool:
    """네이버 로그인 상태 확인 (카페 글쓰기 접근 가능 여부)."""
    await page.goto("https://www.naver.com")
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(2000)
    await screenshot(page, "check_login_status")
    # 로그인 상태면 naver.com에서 로그인 관련 입력 폼이 없음
    # JS로 쿠키 확인: NID_AUT 또는 NID_SES 쿠키가 있으면 로그인 상태
    has_auth = await page.evaluate("""() => {
        return document.cookie.includes('NID_AUT') || document.cookie.includes('NID_SES');
    }""")
    return has_auth


async def ensure_login(context, page, naver_id: str, naver_pw: str, storage_path: str):
    """쿠키 확인 -> 로그인 필요 시 로그인 -> 쿠키 저장."""
    if os.path.exists(storage_path):
        print(f"[INFO] 저장된 쿠키 로드: {storage_path}")
        is_logged_in = await check_login_status(page)
        if is_logged_in:
            print("[OK] 쿠키로 로그인 확인됨. 스킵.")
            return
        else:
            print("[WARN] 쿠키 만료. 재로그인 필요.")

    print("[INFO] 네이버 로그인 시작...")
    await naver_login(page, naver_id, naver_pw)

    # naver_login이 성공적으로 완료되면 (www.naver.com 도달) 바로 쿠키 저장
    await context.storage_state(path=storage_path)
    print(f"[OK] 쿠키 저장: {storage_path}")


# ── Post Publishing ──────────────────────────────────────


async def publish_single_post(
    page, cafe_id_str: str, menu_id: str, title: str, html_content: str,
    *, submit: bool = True,
) -> str:
    """카페에 단일 포스트 발행. 발행된 URL 반환.

    submit=False이면 에디터 입력까지만 수행 (등록 버튼 미클릭).
    """
    # 글쓰기 페이지 이동
    write_url = f"https://cafe.naver.com/ca-fe/cafes/{cafe_id_str}/menus/{menu_id}/articles/write"
    print(f"  [WRITE] {write_url}")
    await page.goto(write_url)
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(3000)
    await screenshot(page, "10_write_page_loaded")

    # 제목 입력 (Ctrl+A → 삭제 → 타이핑)
    title_input = page.locator("textarea.textarea_input")  # PHASE_B_SELECTOR
    await title_input.click()
    await page.keyboard.press(f"{MODIFIER}+KeyA")
    await page.keyboard.press("Backspace")
    await page.keyboard.type(title, delay=10)
    await page.wait_for_timeout(500)
    await screenshot(page, "11_title_typed")

    # 본문 영역 포커스
    body_area = page.locator("p.se-text-paragraph").first
    await body_area.click()
    await page.wait_for_timeout(500)

    # HTML -> 에디터 액션 변환 + 실행
    actions = html_to_editor_actions(html_content)
    print(f"  [ACTIONS] {len(actions)}개 블록 변환됨")
    await execute_editor_actions(page, actions)
    await page.wait_for_timeout(1000)
    await screenshot(page, "12_body_filled")

    if not submit:
        print("  [TEST] 등록 버튼 미클릭 (submit=False)")
        return page.url

    # 등록 버튼 클릭
    submit_btn = page.locator("a.BaseButton.BaseButton--skinGreen")  # PHASE_B_SELECTOR
    await submit_btn.click()
    await page.wait_for_timeout(5000)
    await screenshot(page, "13_after_submit")

    # 발행 URL 추출
    post_url = page.url
    if "/articles/write" in post_url:
        await screenshot(page, "14_submit_failed")
        raise RuntimeError(f"등록 실패: 여전히 글쓰기 페이지 ({post_url})")

    print(f"  [OK] 발행 완료: {post_url}")
    return post_url


# ── Publish Modes ────────────────────────────────────────


async def run_immediate(page, cafe: dict, args):
    """즉시 모드: 모든 pending 포스트를 바로 발행."""
    posts = fetch_pending_posts(cafe["api_key"])
    if not posts:
        print("[PUBLISH] pending 포스트 없음. 종료.")
        return

    print(f"[PUBLISH] pending 포스트 {len(posts)}개 발행 시작")
    success_count = 0
    fail_count = 0

    for idx, post in enumerate(posts, 1):
        post_id = post["id"]
        post_data = post.get("post", {})
        title = post_data.get("title", "제목 없음")
        html_content = post_data.get("post_context", "")
        cafe_id_str = post.get("cafe_id_str", cafe["cafe_id"])
        menu_id = post.get("menu_id", cafe["menu_id"])

        print(f"\n[{idx}/{len(posts)}] 포스트 #{post_id}: {title}")

        try:
            post_url = await publish_single_post(
                page, cafe_id_str, menu_id, title, html_content
            )
            update_post_status(post_id, post_url)
            print(f"  [API] 상태 업데이트 완료 (published)")
            success_count += 1
        except Exception as e:
            print(f"  [ERROR] 발행 실패: {e}")
            print(f"  [INFO] 상태 유지 (pending) → 다음 실행 시 재시도")
            fail_count += 1

        # 포스트간 딜레이
        if idx < len(posts):
            print(f"  [WAIT] {args.delay}초 대기...")
            await page.wait_for_timeout(args.delay * 1000)

    # 결과 요약
    print(f"\n{'=' * 50}")
    print(f"[RESULT] 총 {len(posts)}개 중 성공: {success_count}, 실패: {fail_count}")
    print(f"{'=' * 50}")


async def _interruptible_sleep(seconds: float, shutdown_event: asyncio.Event):
    """shutdown_event가 set되면 즉시 깨어나는 sleep. Ctrl+C 즉시 반응 가능."""
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass  # 정상: 시간 다 됨


async def run_scheduled(page, context, cafe: dict,
                        naver_id: str, naver_pw: str, storage_path: str, args):
    """스케줄 모드: publish_date에 맞춰 예약 발행. 모든 포스트 완료 시 자동 종료."""
    preset_name = args.preset

    write_pid_file(preset_name)
    print(f"[SCHEDULE] 스케줄 모드 시작 (PID: {os.getpid()})")

    # Graceful shutdown: asyncio Event 기반 (long sleep 중 즉시 반응)
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def handle_signal():
        print(f"\n[SCHEDULE] 종료 신호 수신. 현재 작업 완료 후 종료합니다...")
        shutdown_event.set()

    loop.add_signal_handler(signal.SIGINT, handle_signal)
    loop.add_signal_handler(signal.SIGTERM, handle_signal)

    total_success = 0
    total_fail = 0

    try:
        while not shutdown_event.is_set():
            # 1. pending 포스트 조회 (API 실패 시 재시도)
            try:
                posts = fetch_pending_posts(cafe["api_key"])
            except Exception as e:
                print(f"[SCHEDULE-WARN] API 조회 실패: {e}. 60초 후 재시도...")
                await _interruptible_sleep(60, shutdown_event)
                continue

            # 2. 전부 발행 완료 → 종료
            if not posts:
                print(f"\n{'=' * 50}")
                print(f"[SCHEDULE] 모든 포스트 발행 완료. 종료합니다.")
                print(f"[RESULT] 총 성공: {total_success}, 실패: {total_fail}")
                print(f"{'=' * 50}")
                break

            # 3. publish_date 기준 필터
            ready_posts = [p for p in posts if is_publish_time(p)]
            future_posts = [p for p in posts if not is_publish_time(p)]

            if not ready_posts:
                # 아직 발행할 포스트 없음 → smart sleep
                next_time = get_next_publish_time(future_posts)
                if next_time:
                    now = datetime.now(KST)
                    wait_seconds = (next_time - now).total_seconds()
                    sleep_seconds = max(60, wait_seconds)
                    print(f"[SCHEDULE] 대기중 포스트 {len(future_posts)}개. "
                          f"다음 발행: {next_time.strftime('%Y-%m-%d %H:%M:%S')} "
                          f"({int(wait_seconds // 3600)}시간 {int((wait_seconds % 3600) // 60)}분 후)")
                    await _interruptible_sleep(sleep_seconds, shutdown_event)
                else:
                    await _interruptible_sleep(60, shutdown_event)
                continue

            # 4. 브라우저 상태 방어 (장시간 대기 후)
            try:
                await page.evaluate("1+1")
            except Exception:
                print("[SCHEDULE] 브라우저 페이지 복구 중...")
                page = await context.new_page()

            # 5. 로그인 상태 재확인
            try:
                is_logged_in = await check_login_status(page)
                if not is_logged_in:
                    print("[SCHEDULE] 세션 만료 감지. 재로그인...")
                    await ensure_login(context, page, naver_id, naver_pw, storage_path)
            except Exception as e:
                print(f"[SCHEDULE-WARN] 로그인 확인 실패: {e}. 재로그인 시도...")
                try:
                    await ensure_login(context, page, naver_id, naver_pw, storage_path)
                except Exception as login_err:
                    print(f"[SCHEDULE-ERROR] 재로그인 실패: {login_err}. 60초 후 재시도...")
                    await _interruptible_sleep(60, shutdown_event)
                    continue

            # 6. 발행 대상 포스트 처리
            print(f"\n[SCHEDULE] 발행 대상 {len(ready_posts)}개, 대기중 {len(future_posts)}개")

            for idx, post in enumerate(ready_posts, 1):
                if shutdown_event.is_set():
                    break

                post_id = post["id"]
                post_data = post.get("post", {})
                title = post_data.get("title", "제목 없음")
                html_content = post_data.get("post_context", "")
                cafe_id_str = post.get("cafe_id_str", cafe["cafe_id"])
                menu_id = post.get("menu_id", cafe["menu_id"])
                publish_date = post_data.get("publish_date", "N/A")

                print(f"\n[SCHEDULE {idx}/{len(ready_posts)}] 포스트 #{post_id}: {title} (예정: {publish_date})")

                try:
                    post_url = await publish_single_post(
                        page, cafe_id_str, menu_id, title, html_content
                    )
                    update_post_status(post_id, post_url)
                    print(f"  [API] 상태 업데이트 완료 (published)")
                    total_success += 1
                except Exception as e:
                    print(f"  [ERROR] 발행 실패: {e}")
                    print(f"  [INFO] 상태 유지 (pending) → 다음 사이클에 재시도")
                    total_fail += 1

                # 포스트간 딜레이
                if idx < len(ready_posts):
                    print(f"  [WAIT] {args.delay}초 대기...")
                    await page.wait_for_timeout(args.delay * 1000)

        # shutdown 요청으로 종료된 경우
        if shutdown_event.is_set():
            print(f"\n{'=' * 50}")
            print(f"[SCHEDULE] 사용자 종료 요청.")
            print(f"[RESULT] 총 성공: {total_success}, 실패: {total_fail}")
            print(f"{'=' * 50}")

    finally:
        remove_pid_file(preset_name)
        print(f"[SCHEDULE] PID 파일 삭제 완료.")


# ── Main ─────────────────────────────────────────────────


async def run(args):
    # 프리셋 로드
    try:
        with open(PRESETS_PATH, encoding="utf-8") as f:
            presets = json.load(f)
    except FileNotFoundError:
        print("[ERROR] configs/presets.json 파일 없음")
        sys.exit(1)

    if args.preset not in presets:
        print(f"[ERROR] 프리셋 '{args.preset}' 없음. 사용 가능: {', '.join(presets.keys())}")
        sys.exit(1)

    preset = presets[args.preset]
    print(f"[INFO] 프리셋 '{args.preset}' 로드: {preset.get('description', '')}")

    naver_id = preset.get("naver_id")
    naver_pw = preset.get("naver_pw")
    target_id = preset.get("target_id")

    if not naver_id or not naver_pw:
        print("[ERROR] 프리셋에 naver_id/naver_pw 없음")
        sys.exit(1)

    storage_path = os.path.join(CONFIGS_DIR, f"storage_state_{naver_id}.json")

    # 스케줄 모드: 실행 전 중복 체크 (Playwright 시작 전에 빠르게 확인)
    if args.schedule and is_schedule_running(args.preset):
        print(f"[SCHEDULE] 프리셋 '{args.preset}'의 스케줄 발행이 이미 실행 중입니다.")
        print(f"[SCHEDULE] PID 파일: {get_pid_path(args.preset)}")
        return

    # Playwright 시작
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=args.headless)

        # 쿠키 로드 (손상 시 삭제 후 재생성)
        loaded_storage = None
        if os.path.exists(storage_path):
            try:
                with open(storage_path, encoding="utf-8") as f:
                    json.load(f)  # JSON 유효성 검증
                loaded_storage = storage_path
            except (json.JSONDecodeError, OSError):
                print(f"[WARN] 쿠키 파일 손상 → 삭제: {storage_path}")
                os.remove(storage_path)

        context = await browser.new_context(
            permissions=["clipboard-read", "clipboard-write"],
            storage_state=loaded_storage,
        )
        page = await context.new_page()

        try:
            # Phase A: 로그인
            await ensure_login(context, page, naver_id, naver_pw, storage_path)

            # --test-html 모드: 테스트 HTML로 에디터 검증 (등록 안 함)
            if args.test_html is not None:
                if args.test_html == "__default__":
                    test_html = DEFAULT_TEST_HTML
                    print("[INFO] 기본 테스트 HTML 사용")
                elif os.path.exists(args.test_html):
                    with open(args.test_html, encoding="utf-8") as f:
                        test_html = f.read()
                else:
                    print(f"[INFO] 파일 '{args.test_html}' 없음 → 기본 테스트 HTML 사용")
                    test_html = DEFAULT_TEST_HTML

                cafes = fetch_cafes()
                cafe = next((c for c in cafes if c["id"] == target_id), None)
                if not cafe:
                    cafe = cafes[0] if cafes else None
                if not cafe:
                    print("[ERROR] 카페 없음")
                    return

                print(f"[TEST] 테스트 HTML → 카페 '{cafe['name']}' 에디터 입력 (등록 안 함)")
                await publish_single_post(
                    page,
                    cafe["cafe_id"],
                    cafe["menu_id"],
                    "테스트 제목 (자동 발행 테스트)",
                    test_html,
                    submit=False,
                )
                print("[TEST] 에디터 입력 완료! 브라우저에서 결과를 확인하세요.")
                print("[TEST] 30초 후 브라우저가 닫힙니다...")
                await page.wait_for_timeout(30000)
                return

            # --dry-run 모드: 로그인 + API 조회만
            if args.dry_run:
                print("[DRY-RUN] 로그인 성공. API 조회 시작...")
                cafes = fetch_cafes()
                print(f"[DRY-RUN] 카페 {len(cafes)}개:")
                for c in cafes:
                    print(f"  - [{c['id']}] {c['name']} (cafe_id={c['cafe_id']}, menu_id={c['menu_id']})")

                cafe = next((c for c in cafes if c["id"] == target_id), None)
                if cafe:
                    posts = fetch_pending_posts(cafe["api_key"])
                    print(f"[DRY-RUN] pending 포스트 {len(posts)}개:")
                    for post in posts:
                        post_data = post.get("post", {})
                        print(f"  - [{post['id']}] {post_data.get('title', 'N/A')} "
                              f"(발행예정: {post_data.get('publish_date', 'N/A')})")
                else:
                    print(f"[DRY-RUN] target_id={target_id}에 해당하는 카페 없음")
                print("[DRY-RUN] 완료.")
                return

            # Phase C: 카페 조회 (공통)
            print("[PUBLISH] 카페 목록 조회...")
            cafes = fetch_cafes()
            cafe = next((c for c in cafes if c["id"] == target_id), None)
            if not cafe:
                print(f"[ERROR] target_id={target_id}에 해당하는 카페 없음")
                return

            print(f"[PUBLISH] 카페: {cafe['name']} (cafe_id={cafe['cafe_id']}, menu_id={cafe['menu_id']})")

            # 분기: 스케줄 모드 vs 즉시 모드
            if args.schedule:
                await run_scheduled(page, context, cafe, naver_id, naver_pw, storage_path, args)
            else:
                await run_immediate(page, cafe, args)

        finally:
            cleanup_temp_images()
            await browser.close()


def main():
    parser = argparse.ArgumentParser(description="네이버 카페 자동 발행 (Playwright)")
    parser.add_argument("--preset", type=str, required=True, help="프리셋명 (configs/presets.json)")
    parser.add_argument("--headless", action="store_true", help="헤드리스 모드 (기본: False)")
    parser.add_argument("--delay", type=int, default=5, help="포스트간 딜레이(초) (기본: 5)")
    parser.add_argument("--test-html", nargs="?", const="__default__", default=None, help="테스트용 HTML 파일 경로 (인자 없으면 기본 HTML)")
    parser.add_argument("--dry-run", action="store_true", help="발행 없이 로그인 + API 조회만")
    parser.add_argument("--schedule", action="store_true", help="스케줄 모드: publish_date 기준 예약 발행 (완료 시 자동 종료)")

    args = parser.parse_args()

    if not API_KEY:
        print("[ERROR] ADVERCODER_API_KEY not found in .env")
        sys.exit(1)

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
