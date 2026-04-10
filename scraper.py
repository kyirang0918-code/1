import os
import json
import traceback
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build

# 1. 환경 변수 로드 (GOOGLE_CX 및 GOOGLE_API_KEY 추가)
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


def get_latest_youtube_trends(keywords, max_results=20):
    """YouTube에서 최신 F&B 트렌드 영상을 가져옵니다."""
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
            "description": item["snippet"]["description"][:200],
            "video_id": item["id"]["videoId"],
            "url": f"https://youtube.com/watch?v={item['id']['videoId']}"
        })
    return videos


def get_naver_blog_trends(keyword, max_results=10):
    """네이버 검색 API를 통해 블로그 '내돈내산/솔직후기' 반응을 수집합니다."""
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
                "description": item['description'].replace("<b>", "").replace("</b>", ""),
                "link": item['link']
            } for item in result.get('items', [])]
    except Exception as e:
        print(f"  ⚠️ 네이버 블로그 검색 오류: {e}")
        return []


def get_community_trends(query, max_results=10):
    """Google Custom Search API를 통해 X, 더쿠, 인스티즈를 우회 검색합니다."""
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return []
    
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = service.cse().list(
            q=query, cx=GOOGLE_CX, dateRestrict="w1", num=max_results
        ).execute()
        
        return [{
            "title": item.get('title', ''),
            "snippet": item.get('snippet', ''),
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


def summarize_with_ai(videos_data, blogs_data, community_data, max_retries=5):
    """Gemini AI로 데이터를 분석합니다. 확실하게 동작하는 모델명들로 순차적 폴백(Fallback)합니다."""
    import time
    
    # 503, 404 에러 방지를 위해 구글 API가 보장하는 확실한 모델명들만 배치
    models_to_try = [
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash", 
        "gemini-1.5-pro-latest",
        "gemini-pro",
        "gemini-1.5-flash-8b"
    ]

    prompt = f"""
당신은 대한민국 F&B(식음료) 트렌드 전문 분석가입니다.
아래는 최근 3일간 수집된 유튜브, 네이버 블로그, 그리고 주요 커뮤니티(X, 더쿠, 인스티즈 등)의 데이터입니다.

[유튜브 데이터]
{json.dumps(videos_data, ensure_ascii=False)}

[네이버 블로그 데이터 (내돈내산/솔직후기 반응)]
{json.dumps(blogs_data, ensure_ascii=False)}

[커뮤니티 및 SNS 데이터 (X, 인스티즈, 더쿠 실시간 반응)]
{json.dumps(community_data, ensure_ascii=False)}

[분석 지시]
위 세 가지 데이터를 분석하여, 현재 한국에서 실제로 유행하거나 화제가 되고 있는 구체적인 F&B 아이템 5개를 추출하세요.
단일 출처가 아닌, **여러 출처에서 공통으로 언급되는 유행 아이템**을 최우선으로 선정하세요.

중요:
- "디저트가 유행", "편의점 트렌드" 같은 모호한 양상 표현은 절대 금지.
- 반드시 실제 상품명, 메뉴명, 또는 브랜드명을 중심으로 작성할 것.
- sentiment 값은 반드시 "hot"(지금 난리남), "growing"(상승세), "new"(신상) 중 하나로만 작성.
- keywords 배열에는 실제 검색에 쓸 수 있는 구체적인 단어만 3~5개 넣을 것.
- mentioned_in 배열에는 아이템이 언급된 출처를 "youtube", "naver_blog", "community" 중에서 찾아 모두 넣으세요.
- source_video는 참고한 데이터 중 가장 대표적인 URL 하나를 넣으세요.

[출력 형식] 반드시 아래 JSON만 출력할 것:
{{"updated_at": "{today_str}", "summary": "한 문장으로 핵심 요약", "trends": [{{"id": 1, "title": "구체적인 상품명", "description": "왜 화제인지 2~3문장 설명", "sentiment": "hot", "keywords": ["키워드1", "키워드2"], "mentioned_in": ["youtube", "community"], "source_video": "대표 URL"}}]}}
"""

    data = {"contents": [{"parts": [{"text": prompt}]}]}

    for attempt in range(max_retries):
        current_model = models_to_try[attempt]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={GEMINI_API_KEY}"
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                
                # 마크다운 포맷 파싱 안전장치
                text = text.replace("```json", "").replace("```", "").strip()
                return text
                
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 5
                print(f"   ⚠️ Gemini API 응답 지연 ({e}). [{current_model}] 시도 실패. {wait}초 후 다음 모델로 우회 시도... ({attempt+1}/{max_retries})")
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
        
        # 1. 출처 교차 검증 (mentioned_in 배열 확인)
        sources = trend.get("mentioned_in", [])
        if len(sources) >= 2:
            print(f"   🔥 [교차 검증 성공] '{trend['title']}' - 여러 출처에서 언급됨: {', '.join(sources)}")
            trend["cross_verified"] = True
        else:
            print(f"   ⚠️ [단일 출처 확인] '{trend['title']}' - {', '.join(sources)} 에서만 언급됨")
            trend["cross_verified"] = False

        # 2. 네이버 데이터랩 교차 검증
        naver_result = get_naver_trend(main_keyword)
        if naver_result:
            trend["naver_trend"] = naver_result
            if naver_result["is_rising"] and trend.get("sentiment") == "growing":
                trend["sentiment"] = "hot"  # 네이버에서도 상승 확인되면 hot으로 격상
        print(f"      ↳ 네이버 트렌드 조회 완료: {main_keyword}")
    return trend_data


if __name__ == "__main__":
    try:
        if not YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY 시크릿이 설정되지 않았습니다!")
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY 시크릿이 설정되지 않았습니다!")

        print("1. 유튜브 최신 트렌드 수집 중...")
        recent_videos = get_latest_youtube_trends(
            "편의점 신상 OR 핫플 디저트 OR 먹방 신메뉴 OR 카페 신메뉴 OR 마라탕 OR 탕후루 OR 떡볶이 신메뉴"
        )
        print(f"   → 영상 {len(recent_videos)}개 수집 완료.")

        print("2. 네이버 블로그 '찐 반응' 수집 중...")
        recent_blogs = get_naver_blog_trends("편의점 신상 솔직후기 OR 디저트 내돈내산", max_results=10)
        
        print("3. 커뮤니티(X, 인스티즈, 더쿠) 우회 수집 중...")
        community_query = "(site:twitter.com OR site:x.com OR site:instiz.net OR site:theqoo.net) (편의점 존맛 OR 요즘 유행 디저트 OR 품절)"
        recent_community = get_community_trends(community_query, max_results=10)

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
