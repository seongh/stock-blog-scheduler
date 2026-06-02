#!/bin/bash
# ================================================
# 📝 주식 블로그 자동 생성기 — 로컬 실행
# 더블클릭으로 실행하세요!
# ================================================

# 이 스크립트가 있는 폴더로 이동
cd "$(dirname "$0")"

# 터미널 창 제목
echo -e "\033]0;주식 블로그 생성기\007"

echo ""
echo "================================================"
echo "  📈 주식 블로그 자동 생성기"
echo "================================================"
echo ""

# Python & anthropic 패키지 확인
if ! python3 -c "import anthropic" 2>/dev/null; then
    echo "📦 anthropic 패키지 설치 중..."
    pip3 install anthropic --quiet
fi

# API 키 확인
if [ -z "$ANTHROPIC_API_KEY" ]; then
    # .env 파일에서 불러오기 시도
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ ANTHROPIC_API_KEY가 설정되지 않았습니다."
    echo ""
    echo "   .env 파일에 아래 내용을 저장해 주세요:"
    echo "   ANTHROPIC_API_KEY=sk-ant-xxxxx"
    echo ""
    read -p "   또는 지금 직접 입력하세요: " input_key
    if [ -n "$input_key" ]; then
        export ANTHROPIC_API_KEY="$input_key"
    else
        echo "키가 없어 종료합니다."
        read -p "엔터를 눌러 닫으세요..."
        exit 1
    fi
fi

# 오늘 요일 확인 (KST)
DAY=$(date +%u)  # 1=월, 7=일
HOUR=$(date +%H)

echo "📅 오늘: $(date '+%Y년 %m월 %d일') ($(date '+%A'))"
echo ""
echo "실행할 블로그를 선택하세요:"
echo ""
echo "  [1] 🌅 미국 증시 모닝 브리핑"
echo "  [2] ☀️  한국 증시 TOP5 (오후)"
echo "  [3] 🌙 저녁 시황 & 미국 프리마켓"
echo "  [4] 🌅 주말 아침 — 주간 마무리"
echo "  [5] ☀️  주말 오후 — 글로벌 동향"
echo "  [6] 🌙 일요일 저녁 — 다음 주 전략"
echo ""
echo "  [0] 오늘 날짜에 맞게 자동 선택"
echo ""
read -p "선택 (0-6): " choice

case $choice in
    1) TASK="stock-blog-morning" ;;
    2) TASK="stock-blog-noon" ;;
    3) TASK="stock-blog-evening" ;;
    4) TASK="stock-blog-weekend-morning" ;;
    5) TASK="stock-blog-weekend-noon" ;;
    6) TASK="stock-blog-weekend-evening" ;;
    0)
        # 자동 선택: 시간 기준
        if [ $HOUR -lt 11 ]; then
            if [ $DAY -ge 6 ]; then
                TASK="stock-blog-weekend-morning"
            else
                TASK="stock-blog-morning"
            fi
        elif [ $HOUR -lt 15 ]; then
            if [ $DAY -ge 6 ]; then
                TASK="stock-blog-weekend-noon"
            else
                TASK="stock-blog-noon"
            fi
        else
            if [ $DAY -eq 7 ]; then
                TASK="stock-blog-weekend-evening"
            elif [ $DAY -ge 6 ]; then
                TASK="stock-blog-weekend-noon"
            else
                TASK="stock-blog-evening"
            fi
        fi
        echo "자동 선택: $TASK"
        ;;
    *)
        echo "잘못된 선택입니다."
        read -p "엔터를 눌러 닫으세요..."
        exit 1
        ;;
esac

echo ""
echo "================================================"
echo "  🚀 블로그 생성 시작: $TASK"
echo "  ⏱  약 3~5분 소요됩니다..."
echo "================================================"
echo ""

python3 run_task.py "$TASK"

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "  ✅ 블로그 생성 완료!"
    # 생성된 파일 열기
    LAST=$(cat .last_output 2>/dev/null)
    if [ -n "$LAST" ] && [ -f "$LAST" ]; then
        echo "  📄 생성된 파일: $LAST"
        echo ""
        read -p "  파일을 열어볼까요? (y/n): " open_file
        if [ "$open_file" = "y" ] || [ "$open_file" = "Y" ]; then
            open "$LAST"
        fi
    fi
    echo "================================================"
else
    echo ""
    echo "❌ 블로그 생성 중 오류가 발생했습니다."
    echo "   위의 오류 메시지를 확인해 주세요."
fi

echo ""
read -p "엔터를 눌러 닫으세요..."
