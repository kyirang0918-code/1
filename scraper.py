import os
import json
import traceback
import urllib.request
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build

# 보이지 않는 공백이나 엔터 기호가 딸려오는 것을 강제로 잘라내는 .strip() 백신 추가!
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""당신은 트렌드 분석가입니다. 최근 유튜브 데이터에서 F&B 트렌드 3개를 추출해 JSON으로 답하세요. 데이터: {json.dumps(videos_data, ensure_ascii=False)} 
    출력형식: {{"updated_at": "{datetime.now().strftime('%Y-%m-%d')}", "summary": "요약", "trends": [{{"id": 1, "title": "제목", "description": "설명", "sentiment": "hot", "keywords": ["키워드"], "source_video": "링크"}}]}}"""
    
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        text = result['candidates'][0]['content']['parts'][0]['text']
        text = text.strip()
        if text.startswith('```json'): text = text[7:]
        if text.startswith('```'): text = text[3:]
        if text.endswith('```'): text = text[:-3]
        return text.strip()

if __name__ == "__main__":
    try:
        if not YOUTUBE_API_KEY or not GEMINI_API_KEY:
            raise ValueError("API 키가 아예 비어있습니다!")

        recent_videos = get_latest_youtube_trends("편의점 신상 OR 핫플 디저트 OR 디저트 먹방 OR 카페 오픈런 OR 디저트 유행")
        ai_json_result = summarize_with_ai(recent_videos)
        
        with open("data.js", "w", encoding="utf-8") as f:
            f.write(f"const trendData = {ai_json_result};\n")
            
        print("정상적으로 업데이트를 완료했습니다.")

    except Exception as e:
        error_msg = traceback.format_exc()
        # 오류가 나더라도, 사용 중인 키의 앞 5자리를 반환해 진짜 제미나이 키인지 최종 검증합니다.
        error_data = {"error": str(e), "traceback": error_msg[-500:], "key_check": GEMINI_API_KEY[:5]}
        with open("data.js", "w", encoding="utf-8") as f:
            f.write(f"const trendData = {json.dumps(error_data, ensure_ascii=False)};\n")
