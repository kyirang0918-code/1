import os
import json
import traceback
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
import google.generativeai as genai

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

time_limit = datetime.now(timezone.utc) - timedelta(days=3)
three_days_ago = time_limit.strftime('%Y-%m-%dT%H:%M:%SZ')

def get_latest_youtube_trends(keywords, max_results=15):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.search().list(part="snippet", q=keywords, type="video", order="viewCount", publishedAfter=three_days_ago, maxResults=max_results)
    response = request.execute()
    videos = []
    for item in response.get("items", []):
        videos.append({"title": item["snippet"]["title"], "description": item["snippet"]["description"], "video_id": item["id"]["videoId"], "url": f"https://youtube.com/watch?v={item['id']['videoId']}"})
    return videos

def summarize_with_ai(videos_data):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""당신은 트렌드 분석가입니다. 최근 유튜브 데이터에서 F&B 트렌드 3개를 추출해 JSON으로 답하세요. 데이터: {json.dumps(videos_data, ensure_ascii=False)} 
    출력형식: {{"updated_at": "{datetime.now().strftime('%Y-%m-%d')}", "summary": "요약", "trends": [{{"id": 1, "title": "제목", "description": "설명", "sentiment": "hot", "keywords": ["키워드"], "source_video": "링크"}}]}}"""
    return model.generate_content(prompt).text

if __name__ == "__main__":
    try:
        if not YOUTUBE_API_KEY:
            raise ValueError("깃허브 우측상단 Settings -> Secrets에 YOUTUBE_API_KEY 이름이 틀렸거나 등록이 안 되었습니다!")
        if not GEMINI_API_KEY:
            raise ValueError("깃허브 Settings -> Secrets에 GEMINI_API_KEY 등록이 누락되었습니다!")

        recent_videos = get_latest_youtube_trends("편의점 신상 OR 핫플 디저트 OR 디저트 먹방")
        ai_json_result = summarize_with_ai(recent_videos)
        
        with open("data.js", "w", encoding="utf-8") as f:
            f.write(f"const trendData = {ai_json_result.strip()};\n")
            
        print("정상적으로 업데이트를 완료했습니다.")

    except Exception as e:
        # 에러가 나면 뻗어버리지 않고, 에러의 원인을 화면에 띄우도록 JS 파일로 저장함
        error_msg = traceback.format_exc()
        error_data = {"error": str(e), "traceback": error_msg[-500:]}
        with open("data.js", "w", encoding="utf-8") as f:
            f.write(f"const trendData = {json.dumps(error_data, ensure_ascii=False)};\n")
        print("에러 덫에 걸렸습니다! 로그를 data.js에 기록했습니다.")
