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
    
    # 1단계: 일단 넉넉하게 15개를 가져옵니다.
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
        if view_count >= 5000 or like_count >= 50:
            videos.append({
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"][:100],
                "url": f"https://youtube.com/watch?v={item['id']}"
            })
            
            print(f"   🔥 [검증 통과] 조회수: {view_count} / 좋아요: {like_count} - {item['snippet']['title'][:20]}...")
            
        if len(videos) >= max_results:
            break
            
    return videos


def get_naver_blog_trends(keyword, max_results=7):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []
    
    encText = urllib.parse.quote(keyword)
    url = f"https://openapi.naver.com/v1/search/blog?query={encText}&display=30&sort=date"
    req = urllib.request.Request(url, headers={
        'X-Naver-Client-Id': NAVER_CLIENT_ID,
        'X-Naver-Client-Secret': NAVER_CLIENT_SECRET
    })
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            three_days_ago_date = (datetime.now() - timedelta(days=3)).strftime('%Y%m%d')
            spam_keywords = ["소정의 원고료", "제공받아", "업체로부터", "협찬", "지원받아"]
            filtered_blogs = []
            
            for item in result.get('items', []):
                if item.get('postdate', '') >= three_days_ago_date:
                    desc_text = item['description'].replace("<b>", "").replace("</b>", "")
                    
                    if any(spam in desc_text for spam in spam_keywords):
                        continue 
                        
                    filtered_blogs.append({
                        "title": item['title'].replace("<b>", "").replace("</b>", ""),
                        "description": desc_text[:100],
                        "link": item['link']
                    })
                
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
            dateRestrict="d3", 
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


def summarize_with_ai(videos_data, blogs_data, community_data, max_retries=3):
    import time

    # 확실하게 구동되는 최신 공식 모델들로만 재배치
    MODEL_FALLBACKS = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash"
    ]

    prompt = f"""
당신은 대한민국 F&B(식음료) 트렌드 전문 분석가입니다.
아래는 최근 3일간 수집된 유튜브, 네이버 블로그, 커뮤니티 데이터입니다.

[유튜브]
{json.dumps(videos_data, ensure_ascii=False)}

[네이버 블로그]
{json.dumps(blogs_data, ensure_ascii=False)}

[커뮤니티/SNS]
{json.dumps(community_data, ensure_ascii=False)}

위 [수집된 데이터]만을 바탕으로 현재 한국에서 화제인 F&B 아이템을 추출하세요.

🚨 [매우 중요한 엄격한 규칙] 🚨
1. 절대 지어내지 마세요: 반드시 위 데이터에 존재하는 아이템만 추출하세요. 과거의 유행(예: 두바이 초콜릿 등)을 임의로 추가하면 안 됩니다.
2. 억지로 채우지 마세요: 확실한 트렌드가 3개뿐이라면 3개만 출력하세요. 5개를 무리해서 채울 필요 없습니다. (최대 5개)
3. 중복 금지: 중복되거나 유사한 아이템(예: '버터떡'과 'CU 버터떡')은 반드시 하나의 항목으로 통합하세요.
4. 출처 표기: 아이템을 도출하는 데 가장 큰 도움이 된 데이터의 URL 하나를 `source_link`에 넣고, 그 출처가 어디인지 `source_name`("유튜브", "네이버 블로그", "커뮤니티" 중 택 1)에 적어주세요.

아래 JSON 형식으로만 출력하세요. 백틱(```)이나 추가 설명 없이 순수 JSON만 출력하세요.
{{
  "updated_at": "{today_str}",
  "summary": "오늘의 트렌드 핵심 요약 한 문장",
  "trends": [
    {{
      "title": "상품명 (정확하게)",
      "description": "화제 이유 2~3문장 요약",
      "sentiment": "hot",
      "keywords": ["키워드1", "키워드2"],
      "mentioned_in": ["youtube", "naver_blog", "community"],
      "source_link": "URL",
      "source_name": "출처명"
    }}
  ]
}}
"""

    data = {"contents": [{"parts": [{"text": prompt}]}]}
    last_error = None

    for model in MODEL_FALLBACKS:
        url = f"[https://generativelanguage.googleapis.com/v1beta/models/](https://generativelanguage.googleapis.com/v1beta/models/){model}:generateContent?key={GEMINI_API_KEY}"
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
                    
                    # ✅ JSON 변환 에러의 주범인 '군더더기 텍스트'를 잘라내는 확실한 파싱 로직
                    start_idx = text.find('{')
                    end_idx = text.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        text = text[start_idx:end_idx+1]
                    else:
                        text = text.replace("```json", "").replace("```", "").strip()
                        
                    print(f"   ✅ 성공: {model}")
                    return text

            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8') if e.fp else ""
                last_error = f"HTTP {e.code}: {error_body[:200]}"
                print(f"   ⚠️ {last_error}")
                
                # ✅ 429 에러 시 무조건 탈주하지 않고 65초 대기 후 살려냅니다.
                if e.code == 429:
                    print(f"   ⏳ 무료 할당량 초과(429). 65초 대기 후 재시도합니다...")
                    time.sleep(65)
                    continue 
                elif e.code == 404:
                    print(f"   ❌ 해당 모델 없음(404). 즉시 다음 모델로 우회합니다.")
                    break 
                elif e.code in (500, 503):
                    print(f"   ⏳ 서버 과부하({e.code}). 15초 대기 후 재시도합니다...")
                    time.sleep(15)
                    continue
                else:
                    break

            except Exception as e:
                last_error = str(e)
                print(f"   ⚠️ 네트워크 오류: {e}")
                time.sleep(10)

    raise RuntimeError(f"모든 제미나이 모델 시도 실패. 마지막 에러: {last_error}")


def enrich_with_naver_trends(trend_data):
    if not NAVER_CLIENT_ID:
        print("네이버 API 키 없음. 건너뜁니다.")
        return trend_data

    for trend in trend_data.get("trends", []):
        main_keyword = trend.get("keywords", [trend.get("title", "")])[0]
        sources = trend.get("mentioned_in", [])

        if len(sources) >= 2:
            print(f"   🔥 [교차검증 성공] '{trend['title']}' - {', '.join(sources)}")
            trend["cross_verified"] = True
        else:
            print(f"   ⚠️ [단일 출처] '{trend['title']}' - {', '.join(sources)}")
            trend["cross_verified"] = False

        naver_result = get_naver_trend(main_keyword)
        if naver_result:
            trend["naver_trend"] = naver_result
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
            "편의점 신상 OR 신상 디저트 OR 디저트 유행 OR 유행 막차",
            max_results=7
        )
        print(f"   → 영상 {len(recent_videos)}개 수집 완료.")

        print("2. 네이버 블로그 수집 중...")
        recent_blogs = get_naver_blog_trends("편의점 신상 유행 디저트 내돈내산", max_results=7)

        print("3. 커뮤니티 수집 중...")
        community_query = "(site:twitter.com OR site:x.com OR site:instiz.net OR site:theqoo.net) (편의점 신상 OR 신상 디저트 OR 유행 막차 OR 품절)"
        recent_community = get_community_trends(community_query, max_results=7)

        print("4. Gemini AI 트렌드 분석 중...")
        ai_json_str = summarize_with_ai(recent_videos, recent_blogs, recent_community)
        
        # 여기서 발생하는 JSONDecodeError 원천 차단
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
