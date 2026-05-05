#!/usr/bin/env python3
"""
네이버 블로그 자동 포스팅 스크립트
Selenium을 사용해 GitHub Actions에서 네이버 블로그에 글을 자동 게시합니다.

필요한 GitHub Secrets:
  NAVER_ID  - 네이버 아이디
  NAVER_PW  - 네이버 비밀번호

사용법:
  python naver_post.py <markdown_file_path>
  python naver_post.py  # .last_output 파일에서 경로 자동 읽기
"""

import os
import sys
import re
import time
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
except ImportError:
    print("❌ selenium이 설치되지 않았습니다. pip install selenium 실행 후 재시도하세요.")
    sys.exit(1)


# ─────────────────────────────────────────
# 1. 파일 읽기 및 파싱
# ─────────────────────────────────────────

def get_output_file() -> Path:
    """포스팅할 마크다운 파일 경로를 반환합니다."""
    if len(sys.argv) >= 2:
        path = Path(sys.argv[1])
    else:
        last = Path(".last_output")
        if not last.exists():
            print("❌ .last_output 파일이 없습니다. run_task.py를 먼저 실행하세요.")
            sys.exit(1)
        path = Path(last.read_text(encoding="utf-8").strip())

    if not path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {path}")
        sys.exit(1)

    return path


def parse_blog(filepath: Path):
    """마크다운에서 제목·태그·본문을 추출합니다."""
    content = filepath.read_text(encoding="utf-8")

    # 제목 추출 (첫 번째 # 헤딩)
    title = filepath.stem  # 기본값
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            break

    # 태그 추출 — 본문 첫 줄의 #태그 라인
    tags = []
    for line in content.split("\n")[:5]:  # 처음 5줄 안에서 태그 라인 탐색
        found = re.findall(r"#([^\s#]+)", line)
        if len(found) >= 5:  # 태그가 5개 이상이면 태그 라인으로 판단
            tags = found[:30]
            break

    return title, content, tags


# ─────────────────────────────────────────
# 2. Selenium 드라이버 설정
# ─────────────────────────────────────────

def build_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    # webdriver 속성 숨기기 (봇 탐지 우회)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


# ─────────────────────────────────────────
# 3. 네이버 로그인
# ─────────────────────────────────────────

def naver_login(driver, naver_id: str, naver_pw: str) -> bool:
    """네이버에 로그인합니다. 성공하면 True, 실패하면 False를 반환합니다."""
    wait = WebDriverWait(driver, 15)

    driver.get(
        "https://nid.naver.com/nidlogin.login"
        "?mode=form&url=https%3A%2F%2Fwww.naver.com"
    )
    time.sleep(2)

    # JavaScript로 ID/PW 입력 (키 입력 봇 탐지 우회)
    driver.execute_script(
        "document.getElementById('id').value = arguments[0];"
        "document.getElementById('pw').value = arguments[1];",
        naver_id,
        naver_pw,
    )
    time.sleep(0.5)

    driver.find_element(By.ID, "log.login").click()
    time.sleep(3)

    cur = driver.current_url
    # 새 기기 인증 요구 감지
    if any(k in cur for k in ["safty", "new_device", "phoneauth", "certify"]):
        print("⚠️  새 기기 인증이 요청됩니다.")
        print("   해결 방법: 로컬 PC에서 한 번 네이버에 로그인하여 기기를 신뢰 등록하세요.")
        print("   자세한 내용은 README의 '초기 설정' 섹션을 참조하세요.")
        return False

    # 로그인 성공 여부 확인
    if "nidlogin" not in cur:
        print(f"✅ 네이버 로그인 성공 (ID: {naver_id})")
        return True

    print("❌ 네이버 로그인 실패 — ID/PW를 확인하세요.")
    return False


# ─────────────────────────────────────────
# 4. 블로그 포스팅
# ─────────────────────────────────────────

def post_to_naver(driver, naver_id: str, title: str, content: str, tags: list) -> bool:
    """블로그 글을 작성하고 발행합니다."""
    wait = WebDriverWait(driver, 30)

    # 글쓰기 페이지 이동
    driver.get(f"https://blog.naver.com/PostWriteForm.naver?blogId={naver_id}")
    time.sleep(4)

    # mainFrame으로 전환
    try:
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
    except TimeoutException:
        print("❌ 블로그 편집기 로딩 실패 (mainFrame)")
        driver.save_screenshot("naver_error.png")
        return False

    time.sleep(2)

    # ── 제목 입력 ──
    try:
        title_el = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".se-title-text"))
        )
        title_el.click()
        driver.execute_script(
            "arguments[0].innerText = arguments[1];", title_el, title
        )
        time.sleep(0.5)
        print(f"  📝 제목 입력: {title[:50]}...")
    except TimeoutException:
        print("❌ 제목 입력 영역을 찾지 못했습니다.")
        driver.save_screenshot("naver_error.png")
        return False

    # ── 본문 입력 ──
    try:
        body_el = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".se-main-container"))
        )
        body_el.click()
        time.sleep(0.5)

        # 첫 번째 단락 클릭 후 전체 선택 → 내용 삽입
        first_para = driver.find_element(
            By.CSS_SELECTOR, ".se-component.se-text .se-text-paragraph"
        )
        first_para.click()
        time.sleep(0.3)

        driver.execute_script(
            """
            const el = arguments[0];
            const text = arguments[1];
            el.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, text);
            """,
            first_para,
            content,
        )
        time.sleep(1)
        print(f"  📄 본문 입력 완료 ({len(content):,} 글자)")
    except Exception as e:
        print(f"❌ 본문 입력 실패: {e}")
        driver.save_screenshot("naver_error.png")
        return False

    # ── 태그 입력 ──
    if tags:
        try:
            tag_area = driver.find_element(
                By.CSS_SELECTOR, ".se-tag-input, input[placeholder*='태그'], .tag_input"
            )
            for tag in tags[:10]:  # 네이버 블로그 최대 10개 태그
                tag_area.send_keys(tag)
                tag_area.send_keys(Keys.RETURN)
                time.sleep(0.2)
            print(f"  🏷️  태그 입력: {', '.join(tags[:10])}")
        except NoSuchElementException:
            print("  ⚠️ 태그 입력란을 찾지 못했습니다. (태그 없이 발행)")

    # ── 발행 버튼 ──
    driver.switch_to.default_content()
    time.sleep(1)

    try:
        publish_btn = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button.publish_btn__m, .btn_publish, button[class*='publish']")
            )
        )
        publish_btn.click()
        time.sleep(2)

        # 발행 확인 팝업이 뜨면 OK 클릭
        try:
            confirm_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".btn_ok, button[class*='confirm']")
                )
            )
            confirm_btn.click()
            time.sleep(2)
        except TimeoutException:
            pass  # 팝업 없으면 그냥 진행

        print(f"✅ 네이버 블로그 발행 완료!")
        return True

    except TimeoutException:
        print("❌ 발행 버튼을 찾지 못했습니다.")
        driver.save_screenshot("naver_error.png")
        return False


# ─────────────────────────────────────────
# 5. 메인
# ─────────────────────────────────────────

def main():
    naver_id = os.environ.get("NAVER_ID", "").strip()
    naver_pw = os.environ.get("NAVER_PW", "").strip()

    if not naver_id or not naver_pw:
        print("❌ NAVER_ID / NAVER_PW 환경변수가 설정되지 않았습니다.")
        print("   GitHub Repository → Settings → Secrets 에서 추가하세요.")
        sys.exit(1)

    filepath = get_output_file()
    print(f"📂 포스팅 대상 파일: {filepath}")

    title, content, tags = parse_blog(filepath)
    print(f"  제목: {title[:60]}")
    print(f"  태그 {len(tags)}개: {' '.join(['#'+t for t in tags[:8]])}...")

    driver = build_driver()
    try:
        if not naver_login(driver, naver_id, naver_pw):
            print("⏭️  로그인 실패로 네이버 포스팅을 건너뜁니다.")
            sys.exit(0)  # 워크플로우 실패 처리 안 함

        success = post_to_naver(driver, naver_id, title, content, tags)
        if not success:
            print("⏭️  포스팅 실패. 다음 실행 시 재시도됩니다.")
            sys.exit(0)  # 워크플로우 실패 처리 안 함

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
