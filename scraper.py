import os
import json
import traceback
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build

# 1. 환경 변수 로드
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "").strip()
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
GOOGLE_CX = os.environ.get("GOOGLE_CX", "").strip()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()

# 시간 설정
time_limit = datetime.now(timezone.utc) - timedelta(days=3)
three_days_ago = time_limit.strftime('%Y-%m-%dT%H:%M:%SZ')
today_str = datetime.now().strftime('%Y-%m-%d')
one_month_ago_str = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')


def get_latest_youtube_trends(keywords, max_results=5):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.search().list(
        part="snippet", q=keywords, type="video",
        order="viewCount", publishedAfter=three_days_ago, maxResults=max_results
    )
    response = request.execute()
    videos = []
    for item in response.get("items", []):
        videos.append({
            "title": item["snippet"]["title"],
            "description": item["snippet"]["description"][:100],
            "url": f"https://youtube.com/watch?v={item['id']['videoId']}"
        })
    return videos


def get_naver_blog_trends(keyword, max_results=5):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []
    encText = urllib.parse.quote(keyword)
    url = f"https://openapi.naver.com/v1/search/blog?query={encText}&display={max_results}&sort=sim"
    req = urllib.request.Request(url, headers={
        'X-Naver-Client-Id': NAVER_CLIENT_ID,
        'X-Naver-Client-Secret': NAVER_CLIENT_SECRET
    })
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return [{
                "title": item['title'].replace("<b>", "").replace("</b>", ""),
                "description": item['description'].replace("<b>", "").replace("</b>", "")[:100],
                "link": item['link']
            } for item in result.get('items', [])]
    except Exception as e:
        print(f"  ⚠️ 네이버 블로그 검색 오류: {e}")
        return []


def get_community_trends(query, max_results=5):
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return []
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = service.cse().list(
            q=query, cx=GOOGLE_CX, dateRestrict="w1", num=max_results
        ).execute()
        return [{
            "title": item.get('title', ''),
            "snippet": item.get('snippet', '')[:100],
            "link": item.get('link', '')
        } for item in res.get("items", [])]
    except Exception as e:
        print(f"  ⚠️ 구글 커스텀 검색 오류: {e}")
        return []


def get_naver_trend(keyword):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return None
    url = "https://openapi.naver.com/v1/datalab/search"
    body = json.dumps({
        "startDate": one_month_ago_str,
        "endDate": today_str,
        "timeUnit": "week",
        "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}]
    }).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json',
        'X-Naver-Client-Id': NAVER_CLIENT_ID,
        'X-Naver-Client-Secret': NAVER_CLIENT_SECRET
    })
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            ratios = [d['ratio'] for d in result['results'][0]['data']]
            is_rising = ratios[-1] > ratios[0] if len(ratios) >= 2 else True
            return {"ratios": ratios, "is_rising": is_rising}
    except Exception:
        return None


def summarize_with_ai(videos_data, blogs_data, community_data, max_retries=2):
    import time

    # ✅ RPD 여유 순으로 정렬: Flash(250) → Flash-Lite(1000) → 1.5-flash(구형이지만 안정)
    MODEL_FALLBACKS = [
        "gemini-2.0-flash",           # 기본: 안정적
        "gemini-2.5-flash-lite",      # 1차 폴백: RPD 1,000으로 가장 넉넉
        "gemini-1.5-flash",           # 최후 보루: 구형이지만 거의 막히지 않음
    ]

    prompt = f"""... (기존 프롬프트 그대로) ..."""

    data = {"contents": [{"parts": [{"text": prompt}]}]}

    last_error = None
    for model in MODEL_FALLBACKS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        print(f"   🤖 모델 시도: {model}")

        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(data).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req, timeout=60) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    text = text.replace("```json", "").replace("```", "").strip()
                    print(f"   ✅ 성공: {model}")
                    return text

            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8') if e.fp else ""
                last_error = f"HTTP {e.code}: {error_body[:200]}"
                print(f"   ⚠️ {last_error}")

                if e.code == 429:
                    # RPD 소진 → 재시도해도 의미 없으니 즉시 다음 모델로
                    print(f"   ❌ RPD 소진. 다음 모델로 전환.")
                    break
                elif e.code in (404, 400):
                    # 모델 없음 → 즉시 다음 모델로
                    print(f"   ❌ 모델 '{model}' 사용 불가. 다음 모델로 전환.")
                    break
                elif e.code in (500, 503):
                    time.sleep(10)  # 서버 과부하는 잠깐 기다렸다 재시도

            except Exception as e:
                last_error = str(e)
                print(f"   ⚠️ 네트워크 오류: {e}")
                time.sleep(5)

    raise RuntimeError(f"모든 모델 시도 실패. 마지막 에러: {last_error}")
