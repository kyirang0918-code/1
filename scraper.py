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
    
    # 모델 버전을 1.5-flash 또는 2.0-flash로 수정
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""
    당신은 대한민국 F&B(식음료) 트렌드 전문 분석가입니다.
    # ... (프롬프트 내용은 기존과 동일하게 유지) ...
    """

    # generationConfig를 추가하여 확실한 JSON 응답을 유도
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

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
                
                # generationConfig를 사용하면 마크다운 제거가 굳이 필요 없지만, 안전을 위해 유지
                text = text.replace("```json", "").replace("```", "").strip()
                return text
                
        except urllib.error.HTTPError as e:
            if attempt < max_retries - 1:
                if e.code == 429:
                    wait = 65
                    print(f"   ⚠️ 무료 할당량(RPM) 초과. 리셋을 위해 {wait}초 휴식... ({attempt+1}/{max_retries})")
                elif e.code == 503:
                    # 503 에러 시 재시도 대기 시간을 점진적으로 늘리는 방식을 추천합니다 (Exponential Backoff)
                    wait = 15 * (attempt + 1)
                    print(f"   ⚠️ 구글 서버 과부하(503). {wait}초 후 재시도... ({attempt+1}/{max_retries})")
                else:
                    wait = 10
                    print(f"   ⚠️ API 오류 ({e.code}). {wait}초 후 재시도... ({attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                error_body = e.read().decode('utf-8') if e.fp else "알 수 없는 에러"
                print(f"❌ 최종 에러 사유: {e.code} - {error_body}")
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 10
                print(f"   ⚠️ 네트워크 지연 ({e}). {wait}초 후 재시도... ({attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                raise


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
