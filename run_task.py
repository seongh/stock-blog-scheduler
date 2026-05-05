#!/usr/bin/env python3
"""
Stock Blog Scheduler - GitHub Actions Runner
노트북이 꺼져 있어도 Anthropic API를 통해 주식 블로그를 자동 작성합니다.

Usage: python run_task.py <task-name>
Tasks:
  stock-blog-morning           평일 아침 - 미국 증시 브리핑
  stock-blog-noon              평일 오후 - 한국 증시 TOP5
  stock-blog-evening           평일 저녁 - 한국 마감 & 미국 프리마켓
  stock-blog-weekend-morning   토일 아침 - 주간 마무리 리포트
  stock-blog-weekend-noon      토일 오후 - 글로벌 동향 & 섹터 전략
  stock-blog-weekend-evening   토일 저녁 - 다음 주 투자 전략
"""
import anthropic
import os
import sys
import time
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# KST timezone (UTC+9)
KST = timezone(timedelta(hours=9))

# 파일명 패턴 (task명 → 저장 파일명)
FILENAME_MAP = {
    "stock-blog-morning":          "미국증시_{date}.md",
    "stock-blog-noon":             "한국증시_TOP5_{date}.md",
    "stock-blog-evening":          "저녁시황_{date}.md",
    "stock-blog-weekend-morning":  "주간마무리_{date}.md",
    "stock-blog-weekend-noon":     "주말시황_{date}.md",
    "stock-blog-weekend-evening":  "주말저녁_{date}.md",
}


def run_task(task_name: str) -> bool:
    """지정된 태스크를 Anthropic API로 실행합니다."""

    # 프롬프트 파일 로드
    prompt_path = Path(f"tasks/{task_name}.md")
    if not prompt_path.exists():
        print(f"❌ 프롬프트 파일을 찾을 수 없습니다: {prompt_path}")
        sys.exit(1)

    base_prompt = prompt_path.read_text(encoding="utf-8")

    # 현재 날짜 (KST 기준)
    now_kst = datetime.now(KST)
    today = now_kst.strftime("%Y-%m-%d")
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][now_kst.weekday()]

    # GitHub Actions 환경용 안내 추가
    adapted_prompt = base_prompt + f"""

---

## ⚙️ 실행 환경 (GitHub Actions)

- 오늘 날짜: {today} ({weekday_kr}요일) KST
- 파일 저장 도구는 사용할 수 없습니다.
- 블로그 작성이 완료되면 반드시 아래 형식으로 최종 출력하세요:

```
<blog_output filename="파일명.md">
블로그 전체 내용 (마크다운)
</blog_output>
```

WebSearch 도구로 최신 데이터를 충분히 수집한 뒤 작성하세요.
Bash sleep 대신 단순히 재시도하면 됩니다.
"""

    # Anthropic 클라이언트 초기화
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"🚀 태스크 시작: {task_name} | {today} ({weekday_kr}요일)")
    print("=" * 60)

    messages = [{"role": "user", "content": adapted_prompt}]
    max_iterations = 40  # 검색 횟수가 많으므로 여유있게 설정

    for iteration in range(max_iterations):
        try:
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=16000,
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                    }
                ],
                messages=messages,
            )
        except anthropic.APIConnectionError as e:
            print(f"  ⚠️  연결 오류 (시도 {iteration+1}): {e}")
            print("     60초 후 재시도...")
            time.sleep(60)
            continue
        except anthropic.RateLimitError as e:
            print(f"  ⚠️  Rate limit (시도 {iteration+1}): {e}")
            print("     60초 후 재시도...")
            time.sleep(60)
            continue
        except anthropic.APIError as e:
            print(f"  ❌ API 오류: {e}")
            time.sleep(30)
            continue

        # 응답 내용 로깅
        for block in response.content:
            if hasattr(block, "type"):
                if block.type == "tool_use" and block.name == "web_search":
                    query = block.input.get("query", "")
                    print(f"  🔍 검색: {query[:70]}")
                elif block.type == "text" and block.text and len(block.text) > 50:
                    # 블로그 내용이 출력되기 시작하면 표시
                    if "<blog_output" in block.text:
                        print(f"  ✍️  블로그 작성 완료 ({len(block.text):,} 글자)")
                    elif len(block.text) > 200:
                        print(f"  📝 중간 생성 ({len(block.text):,} 글자)...")

        # 메시지 히스토리에 추가
        messages.append({"role": "assistant", "content": response.content})

        # 완료 확인
        if response.stop_reason == "end_turn":
            full_text = "".join(
                block.text for block in response.content
                if hasattr(block, "type") and block.type == "text"
            )
            print("  ✅ 생성 완료!")
            return save_output(full_text, task_name, today)

        # 도구 사용 - tool_result 제공 후 계속
        elif response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Search executed successfully by Anthropic servers.",
                    })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        else:
            print(f"  ⚠️  예상치 못한 stop_reason: {response.stop_reason}")
            break

    print("❌ 최대 반복 횟수 초과")
    return False


def save_output(content: str, task_name: str, date_str: str) -> bool:
    """블로그 내용을 파일로 저장합니다."""

    output_dir = Path("outputs") / date_str
    output_dir.mkdir(parents=True, exist_ok=True)

    # <blog_output filename="..."> 태그 파싱
    match = re.search(
        r'<blog_output\s+filename="([^"]+)">\s*(.*?)\s*</blog_output>',
        content,
        re.DOTALL,
    )

    if match:
        filename = match.group(1).strip()
        blog_content = match.group(2).strip()
        print(f"  📁 파일명 감지: {filename}")
    else:
        # 태그가 없으면 기본 파일명 사용
        template = FILENAME_MAP.get(task_name, f"{task_name}_{{date}}.md")
        filename = template.format(date=date_str)
        blog_content = content
        print(f"  📁 기본 파일명 사용: {filename}")

    out_path = output_dir / filename
    out_path.write_text(blog_content, encoding="utf-8")

    size_kb = len(blog_content.encode("utf-8")) / 1024
    print(f"  💾 저장 완료: {out_path} ({size_kb:.1f} KB)")

    # naver_post.py가 참조할 최신 파일 경로 기록
    Path(".last_output").write_text(str(out_path), encoding="utf-8")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    task = sys.argv[1]
    valid_tasks = list(FILENAME_MAP.keys())

    if task not in valid_tasks:
        print(f"❌ 알 수 없는 태스크: {task}")
        print(f"   사용 가능한 태스크: {', '.join(valid_tasks)}")
        sys.exit(1)

    success = run_task(task)
    sys.exit(0 if success else 1)
