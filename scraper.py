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

# 시간 설정 (최근 3일)
time_limit = datetime.now(timezone.utc) - timedelta(days=3)
three_days_ago = time_limit.strftime('%Y-%m-%dT%H:%M:%SZ')
today_str = datetime.now().strftime('%Y-%m-%d')
one_month_ago_str = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')


def get_latest_youtube_trends(keywords, max_results=5):
    """YouTube에서 최신 F&B 트렌드 영상을 가져옵니다. (데이터 다이어트: 5개)"""
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
            "description": item["snippet"]["description"][:100], # 설명도 100자로 줄임
            "video_id": item["id"]["videoId"],
            "url": f"https://youtube.com/watch?v={item['id']['videoId']}"
        })
    return videos


def get_naver_blog_trends(keyword, max_results=5):
    """네이버 검색 API를 통해 블로그 반응을 수집합니다. (데이터 다이어트: 5개)"""
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
    """Google Custom Search API를 통해 커뮤니티를 우회 검색합니다. (데이터 다이어트: 5개)"""
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
    """네이버 데이터랩 API로 특정 키워드의 최근 1달 검색량 트렌드를 조회합니다."""
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


def summarize_with_ai(videos_data, blogs_data, community_data, max_retries=3):
    import time

    MODEL_FALLBACKS = [
        "gemini-2.5-flash-preview-04-17",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]

    prompt = f"""... (기존 프롬프트 그대로) ..."""

    data = {"contents": [{"parts": [{"text": prompt}]}]}

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
                with urllib.request.urlopen(req, timeout=60) as response:  # timeout 원복
                    result = json.loads(response.read().decode('utf-8'))
                    text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    text = text.replace("```json", "").replace("```", "").strip()
                    print(f"   ✅ 성공: {model}")
                    return text

            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8') if e.fp else ""
                print(f"   ⚠️ HTTP {e.code} ({model}): {error_body[:200]}")

                if e.code == 404:
                    break  # 즉시 다음 모델 (대기 없음)
                elif e.code == 429:
                    time.sleep(65)  # 할당량은 어쩔 수 없이 대기
                elif e.code in (500, 503):
                    time.sleep(10)  # ✅ 짧게 (기존 15초 → 10초)
                else:
                    time.sleep(5)

            except Exception as e:
                print(f"   ⚠️ 네트워크 오류: {e}")
                time.sleep(5)  # ✅ 짧게

    raise RuntimeError("모든 Gemini 모델 시도 실패.")


def enrich_with_naver_trends(trend_data):
    """추출된 트렌드 키워드를 네이버 데이터랩으로 교차 검증하여 데이터를 보강합니다."""
    if not NAVER_CLIENT_ID:
        print("네이버 API 키가 없어 네이버 트렌드 교차 검증을 건너뜁니다.")
        return trend_data

    for trend in trend_data.get("trends", []):
        main_keyword = trend.get("keywords", [trend.get("title", "")])[0]
        
        sources = trend.get("mentioned_in", [])
        if len(sources) >= 2:
            print(f"   🔥 [교차 검증 성공] '{trend['title']}' - 여러 출처에서 언급됨: {', '.join(sources)}")
            trend["cross_verified"] = True
        else:
            print(f"   ⚠️ [단일 출처 확인] '{trend['title']}' - {', '.join(sources)} 에서만 언급됨")
            trend["cross_verified"] = False

        naver_result = get_naver_trend(main_keyword)
        if naver_result:
            trend["naver_trend"] = naver_result
            if naver_result["is_rising"] and trend.get("sentiment") == "growing":
                trend["sentiment"] = "hot" 
        print(f"      ↳ 네이버 트렌드 조회 완료: {main_keyword}")
    return trend_data


if __name__ == "__main__":
    try:
        if not YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY 시크릿이 설정되지 않았습니다!")
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY 시크릿이 설정되지 않았습니다!")

        print("1. 유튜브 최신 트렌드 수집 중...")
        # 수집량을 5개로 줄여서 AI의 부담을 덜어줍니다.
        recent_videos = get_latest_youtube_trends(
            "편의점 신상 OR 핫플 디저트 OR 먹방 신메뉴 OR 카페 신메뉴 OR 마라탕 OR 탕후루 OR 떡볶이 신메뉴",
            max_results=5
        )
        print(f"   → 영상 {len(recent_videos)}개 수집 완료.")

        print("2. 네이버 블로그 '찐 반응' 수집 중...")
        recent_blogs = get_naver_blog_trends("편의점 신상 솔직후기 OR 디저트 내돈내산", max_results=5)
        
        print("3. 커뮤니티(X, 인스티즈, 더쿠) 우회 수집 중...")
        community_query = "(site:twitter.com OR site:x.com OR site:instiz.net OR site:theqoo.net) (편의점 존맛 OR 요즘 유행 디저트 OR 품절)"
        recent_community = get_community_trends(community_query, max_results=5)

        print(f"   → 추가 데이터 수집 완료 (블로그: {len(recent_blogs)}개, 커뮤니티: {len(recent_community)}개)")

        print("4. Gemini AI로 다각적 트렌드 분석 및 출처 간 교차 검증 중...")
        ai_json_str = summarize_with_ai(recent_videos, recent_blogs, recent_community)
        trend_data = json.loads(ai_json_str)
        print(f"   → AI 분석 완료. 트렌드 {len(trend_data.get('trends', []))}개 추출.")

        print("5. 네이버 데이터랩으로 교차 검증 중...")
        trend_data = enrich_with_naver_trends(trend_data)

        with open("data.js", "w", encoding="utf-8") as f:
            f.write(f"const trendData = {json.dumps(trend_data, ensure_ascii=False)};\n")

        print("✅ 모든 작업 완료! data.js 업데이트 성공.")

    except Exception as e:
        error_msg = traceback.format_exc()
        error_data = {
            "error": str(e),
            "traceback": error_msg[-600:],
            "key_check": "OK" if GEMINI_API_KEY else "FAIL"
        }
        with open("data.js", "w", encoding="utf-8") as f:
            f.write(f"const trendData = {json.dumps(error_data, ensure_ascii=False)};\n")
        print(f"❌ 에러 발생: {e}")
        raise
