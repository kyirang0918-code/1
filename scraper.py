import os
import json
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
import google.generativeai as genai

# ==========================================
# 1. API 키 설정 (GitHub 시스템 내부 비밀금고에서 불러옴)
# ==========================================
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

# ==========================================
# 2. "최근 3일 기준" 유튜브 전용 날짜 포맷으로 완벽 수정 (에러 방지)
# ==========================================
time_limit = datetime.now(timezone.utc) - timedelta(days=3)
three_days_ago = time_limit.strftime('%Y-%m-%dT%H:%M:%SZ')

def get_latest_youtube_trends(keywords, max_results=15):
    print(f"🎬 최근 3일 유튜브 탐색 중...")
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    
    request = youtube.search().list(
        part="snippet",
        q=keywords,
        type="video",
        order="viewCount",
        publishedAfter=three_days_ago, 
        maxResults=max_results
    )
    response = request.execute()
    
    videos = []
    for item in response.get("items", []):
        videos.append({
            "title": item["snippet"]["title"],
            "description": item["snippet"]["description"],
            "video_id": item["id"]["videoId"],
            "url": f"https://youtube.com/watch?v={item['id']['videoId']}"
        })
    return videos

def summarize_with_ai(videos_data):
    print("🧠 AI(안정된 1.5버전)가 트렌드 요약 중...")
    genai.configure(api_key=GEMINI_API_KEY)
    # 2.0 대신 가장 빠르고 안정적인 모델(1.5-flash)로 변경
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    당신은 트렌드 분석가입니다. 아래 최근 3일치 유튜브 데이터에서 F&B(음식, 디저트, 신상) 관련 트렌드만 정확히 3가지 추출하여 아래 JSON 형식으로만 답하세요. (마크다운은 절대 금지)
    {json.dumps(videos_data, ensure_ascii=False)}
    
    출력형식:
    {{
      "updated_at": "{datetime.now().strftime('%Y-%m-%d')}",
      "summary": "전체 요약",
      "trends": [
        {{ "id": 1, "title": "제목", "description": "설명", "sentiment": "hot", "keywords": ["키워드"], "source_video": "링크" }}
      ]
    }}
    """
    return model.generate_content(prompt).text

if __name__ == "__main__":
    if not YOUTUBE_API_KEY:
        raise ValueError("GitHub Secrets에 키가 없습니다!")
        
    # 가짜 성공 방지를 위해 에러 억제 제거 -> 문제가 생기면 투명하게 깃허브가 빨간 ❌를 띄워줍니다!
    recent_videos = get_latest_youtube_trends("편의점 신상 OR 핫플 디저트 OR 디저트 먹방")
    ai_json_result = summarize_with_ai(recent_videos)
    
    with open("data.js", "w", encoding="utf-8") as f:
        f.write(f"const trendData = {ai_json_result.strip()};\n")
        
    print("✅ 성공적으로 덮어쓰기 완료!")
