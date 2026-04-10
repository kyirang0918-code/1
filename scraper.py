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
    
    # 1단계: 일단 넉넉하게 15개를 가져옵니다. (조회수 순으로 가져와도 최근 3일이라 허수가 많을 수 있음)
    request = youtube.search().list(
        part="id", q=keywords, type="video",
        order="viewCount", publishedAfter=three_days_ago, maxResults=15
    )
    search_response = request.execute()
    
    video_ids = [item['id']['videoId'] for item in search_response.get("items", [])]
    
    if not video_ids:
        return []

    # 2단계: 추출한 Video ID 묶음으로 '통계(statistics)' 정보를 한 번에 요청합니다.
    stats_request = youtube.videos().list(
        part="snippet,statistics",
        id=",".join(video_ids)
    )
    stats_response = stats_request.execute()

    videos = []
    for item in stats_response.get("items", []):
        stats = item.get("statistics", {})
        view_count = int(stats.get("viewCount", 0))
        like_count = int(stats.get("likeCount", 0))
        
        # 💡 핵심 검증 장치: 최소 반응도 필터링
        # 예: 조회수 1,000회 이상 OR 좋아요 50개 이상인 영상만 '진짜 화제'로 취급
        if view_count >= 1000 or like_count >= 50:
            videos.append({
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"][:100],
                "url": f"https://youtube.com/watch?v={item['id']}"
            })
            
            print(f"   🔥 [검증 통과] 조회수: {view_count} / 좋아요: {like_count} - {item['snippet']['title'][:20]}...")
            
        # 목표한 개수(max_results)를 채우면 즉시 중단
        if len(videos) >= max_results:
            break
            
    return videos


def get_naver_blog_trends(keyword, max_results=7):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []
    
    encText = urllib.parse.quote(keyword)
    # 💡 최신순(date)으로 30개 넉넉히 가져옵니다.
    url = f"https://openapi.naver.com/v1/search/blog?query={encText}&display=30&sort=date"
    req = urllib.request.Request(url, headers={
        'X-Naver-Client-Id': NAVER_CLIENT_ID,
        'X-Naver-Client-Secret': NAVER_CLIENT_SECRET
    })
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            # 3일 전 날짜 세팅
            three_days_ago_date = (datetime.now() - timedelta(days=3)).strftime('%Y%m%d')
            
            # 💡 걸러낼 스팸 키워드를 반복문 시작 전에 한 번만 선언합니다.
            spam_keywords = ["소정의 원고료", "제공받아", "업체로부터", "협찬", "지원받아"]
            filtered_blogs = []
            
            # 💡 반복문은 깔끔하게 딱 한 번만 돕니다!
            for item in result.get('items', []):
                
                # 1단계: 3일 이내에 작성된 최신 글인가?
                if item.get('postdate', '') >= three_days_ago_date:
                    desc_text = item['description'].replace("<b>", "").replace("</b>", "")
                    
                    # 2단계: 본문 요약에 스팸 키워드가 하나라도 있는가?
                    if any(spam in desc_text for spam in spam_keywords):
                        continue # 스팸이면 이 아래 코드는 무시하고 다음 글로 넘어감
                        
                    # 3단계: 날짜도 최신이고 스팸도 아니면 찐 데이터로 추가!
                    filtered_blogs.append({
                        "title": item['title'].replace("<b>", "").replace("</b>", ""),
                        "description": desc_text[:100],
                        "link": item['link']
                    })
                
                # 4단계: 원하는 개수(max_results)를 채웠다면 미련 없이 루프 종료
                if len(filtered_blogs) >= max_results:
                    break
                    
            return filtered_blogs
            
    except Exception as e:
        print(f"  ⚠️ 네이버 블로그 검색 오류: {e}")
        return []


def get_community_trends(query, max_results=7):
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return []
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = service.cse().list(
            q=query, 
            cx=GOOGLE_CX, 
            dateRestrict="d3", # 💡 수정: "w1" (1주일) -> "d3" (3일)로 변경
            num=max_results
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
    """프롬프트는 단순 추출만. 교차검증은 Python에서 별도 처리."""
    import time

    MODEL_FALLBACKS = [
        "gemini-2.0-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
    ]

    # ✅ 프롬프트에서 교차검증 지시 제거 → 가볍게 유지
    # mentioned_in만 AI가 판단하도록 추가 (교차검증 로직은 Python에서)
    prompt = f"""
당신은 대한민국 F&B(식음료) 트렌드 전문 분석가입니다.
아래는 최근 수집된 유튜브, 네이버 블로그, 커뮤니티 데이터입니다.

[유튜브]
{json.dumps(videos_data, ensure_ascii=False)}

[네이버 블로그]
{json.dumps(blogs_data, ensure_ascii=False)}

[커뮤니티/SNS]
{json.dumps(community_data, ensure_ascii=False)}

위 데이터를 바탕으로 현재 한국에서 화제인 F&B 아이템 6개를 추출하세요.

규칙:
- 반드시 실제 상품명, 메뉴명, 브랜드명으로 작성
- "디저트 유행" 같은 모호한 표현 금지
- sentiment는 "hot" / "growing" / "new" 중 하나
- keywords는 실제 검색어 3~6개
- mentioned_in은 아이템이 언급된 출처를 "youtube", "naver_blog", "community" 중에서 모두 표기
- source_video는 참고한 URL 중 하나

아래 JSON만 출력:
{{"updated_at": "{today_str}", "summary": "한 문장 핵심 요약", "trends": [{{"id": 1, "title": "상품명", "description": "화제 이유 2~3문장", "sentiment": "hot", "keywords": ["키워드1", "키워드2"], "mentioned_in": ["youtube", "naver_blog"], "source_video": "URL"}}]}}
"""

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
                if e.code in (429, 404, 400):
                    print(f"   ❌ 다음 모델로 전환.")
                    break
                elif e.code in (500, 503):
                    time.sleep(10)

            except Exception as e:
                last_error = str(e)
                print(f"   ⚠️ 네트워크 오류: {e}")
                time.sleep(5)

    raise RuntimeError(f"모든 모델 시도 실패. 마지막 에러: {last_error}")


def enrich_with_naver_trends(trend_data):
    """
    ✅ 교차검증 + 네이버 트렌드 보강을 Python에서 처리.
    AI 프롬프트가 아닌 코드 레벨에서 수행하므로 속도에 영향 없음.
    """
    if not NAVER_CLIENT_ID:
        print("네이버 API 키 없음. 건너뜁니다.")
        return trend_data

    for trend in trend_data.get("trends", []):
        main_keyword = trend.get("keywords", [trend.get("title", "")])[0]
        sources = trend.get("mentioned_in", [])

        # ✅ 교차검증: 2개 이상 출처에서 언급됐는지 Python에서 판단
        if len(sources) >= 2:
            print(f"   🔥 [교차검증 성공] '{trend['title']}' - {', '.join(sources)}")
            trend["cross_verified"] = True
        else:
            print(f"   ⚠️ [단일 출처] '{trend['title']}' - {', '.join(sources)}")
            trend["cross_verified"] = False

        # ✅ 네이버 데이터랩으로 검색량 보강
        naver_result = get_naver_trend(main_keyword)
        if naver_result:
            trend["naver_trend"] = naver_result
            # ✅ 교차검증 성공 + 상승세면 sentiment 자동 승격
            if naver_result["is_rising"] and trend.get("sentiment") == "growing" and trend["cross_verified"]:
                trend["sentiment"] = "hot"
                print(f"      ↳ sentiment 승격: growing → hot")
        print(f"      ↳ 네이버 트렌드 조회: {main_keyword}")

    return trend_data


if __name__ == "__main__":
    try:
        if not YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY 시크릿이 설정되지 않았습니다!")
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY 시크릿이 설정되지 않았습니다!")

        print("1. 유튜브 최신 트렌드 수집 중...")
        recent_videos = get_latest_youtube_trends(
            "편의점 신상 OR 핫플 디저트 편의점 신상 OR 유행 솔직후기 OR 디저트 내돈내산 OR 유행 막차 OR 신상 디저트",
            max_results=7
        )
        print(f"   → 영상 {len(recent_videos)}개 수집 완료.")

        print("2. 네이버 블로그 수집 중...")
        recent_blogs = get_naver_blog_trends("편의점 신상 OR 유행 솔직후기 OR 디저트 내돈내산 OR 유행 막차 OR 신상 디저트", max_results=7)

        print("3. 커뮤니티 수집 중...")
        community_query = "(site:twitter.com OR site:x.com OR site:instiz.net OR site:theqoo.net) (편의점 신상 OR 요즘 유행 디저트 OR 품절 OR 유행이야 )"
        recent_community = get_community_trends(community_query, max_results=7)
        print(f"   → 블로그 {len(recent_blogs)}개, 커뮤니티 {len(recent_community)}개 수집 완료.")

        print("4. Gemini AI 트렌드 분석 중...")
        ai_json_str = summarize_with_ai(recent_videos, recent_blogs, recent_community)
        trend_data = json.loads(ai_json_str)
        print(f"   → 트렌드 {len(trend_data.get('trends', []))}개 추출 완료.")

        print("5. 교차검증 + 네이버 데이터랩 보강 중...")
        trend_data = enrich_with_naver_trends(trend_data)

        with open("data.js", "w", encoding="utf-8") as f:
            f.write(f"const trendData = {json.dumps(trend_data, ensure_ascii=False)};\n")

        print("✅ 완료! data.js 업데이트 성공.")

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
