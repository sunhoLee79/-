import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import json

# 설정
# 주의: API 키는 보안을 위해 환경 변수나 Streamlit secrets에 저장하는 것이 좋습니다.
API_KEY = 'AIzaSyDLY6YYLqiQ_8YXt5eGFUGIFYvzKaOi-Yk' 
youtube = build('youtube', 'v3', developerKey=API_KEY)

st.set_page_config(page_title="중소형 떡상 스캐너", layout="wide")
st.title("🎯 떡상 스캐너: 중소형 채널 벤치마킹 도구")
st.caption("구독자 대비 조회수가 터진 영상을 찾아 모든 카테고리의 기획 힌트를 얻으세요.")

# 유튜브 카테고리 매핑 (주제 확산을 위한 데이터)
categories = {
    "전체": "",
    "엔터테인먼트": "24",
    "게임": "20",
    "코미디": "23",
    "사람/블로그": "22",
    "노하우/스타일": "26",
    "교육": "27",
    "과학/기술": "28",
    "여행/이벤트": "19",
    "음악": "10"
}

with st.sidebar:
    st.header("⚙️ 필터 설정")
    # 1. 주제 확산: 기본 키워드를 넓게 설정하거나 빈칸으로 유도
    keyword = st.text_input("검색 키워드 (예: 캠핑, 브이로그, 요리, shorts)", "shorts")
    
    # 2. 카테고리 선택 추가
    selected_category_name = st.selectbox("유튜브 카테고리", list(categories.keys()))
    category_id = categories[selected_category_name]
    
    max_results = st.slider("검색 개수 (API 할당량 주의)", 10, 50, 30)
    
    # 구독자 상한선
    sub_limit = st.number_input("구독자 수 상한선 (이하만 표시)", value=100000, step=10000)
    
    # 검색 기간
    days_back = st.slider("며칠 이내 영상?", 7, 90, 30)
    published_after = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"

if st.button("신규 트렌드 분석 시작"):
    try:
        with st.spinner(f"'{keyword}' 관련 '{selected_category_name}' 분야의 데이터를 분석 중..."):
            # 1. 검색 API 호출
            search_params = {
                'q': keyword,
                'part': 'snippet',
                'maxResults': max_results,
                'type': 'video',
                'publishedAfter': published_after,
                'order': 'viewCount' # 조회수 높은 순으로 먼저 검색
            }
            
            # 카테고리 필터 적용 (선택 시)
            if category_id:
                search_params['videoCategoryId'] = category_id

            search_response = youtube.search().list(**search_params).execute()

            if not search_response.get('items'):
                st.warning("검색 결과가 없습니다. 키워드를 변경해 보세요.")
                st.stop()

            video_ids = [item['id']['videoId'] for item in search_response['items']]
            channel_ids = [item['snippet']['channelId'] for item in search_response['items']]

            # 2. 영상 정보 일괄 호출
            video_response = youtube.videos().list(
                part='statistics,snippet',
                id=','.join(video_ids)
            ).execute()

            # 3. 채널 정보 일괄 호출
            channel_response = youtube.channels().list(
                part='statistics,snippet',
                id=','.join(list(set(channel_ids)))
            ).execute()

            channel_info = {}
            for item in channel_response.get('items', []):
                c_id = item.get('id')
                snippet = item.get('snippet', {})
                stats = item.get('statistics', {})
                channel_info[c_id] = {
                    'subs': int(stats.get('subscriberCount', 1)),
                    'title': snippet.get('title', '정보 없음')
                }

            video_data = []
            for v in video_response.get('items', []):
                snippet = v.get('snippet', {})
                stats = v.get('statistics', {})
                c_id = snippet.get('channelId')
                
                c_data = channel_info.get(c_id, {'subs': 1, 'title': '알 수 없음'})
                sub_count = c_data['subs']
                
                # 구독자 상한선 필터링
                if sub_count <= sub_limit:
                    v_id = v.get('id')
                    title = snippet.get('title', '제목 없음')
                    view_count = int(stats.get('viewCount', 0))
                    
                    # 기획 점수 계산 (구독자가 0인 경우 방지)
                    safe_sub_count = sub_count if sub_count > 0 else 1
                    score = round((view_count / safe_sub_count), 2)
                    
                    video_data.append({
                        "기획 점수": score,
                        "채널명": c_data['title'],
                        "제목": title,
                        "조회수": view_count,
                        "구독자 수": sub_count,
                        "링크": f"https://youtu.be/{v_id}"
                    })

            # 4. 결과 출력
            if video_data:
                df = pd.DataFrame(video_data)
                # 기획 점수 높은 순으로 정렬
                df = df.sort_values(by="기획 점수", ascending=False)
                
                display_df = df.copy()
                display_df['조회수'] = display_df['조회수'].apply(lambda x: f"{x:,}")
                display_df['구독자 수'] = display_df['구독자 수'].apply(lambda x: f"{x:,}")
                
                st.dataframe(
                    display_df,
                    column_config={"링크": st.column_config.LinkColumn("영상 링크")},
                    use_container_width=True, 
                    hide_index=True
                )
                st.success(f"✅ 분석 완료! {len(df)}개의 유망한 영상을 찾았습니다.")
            else:
                st.warning(f"구독자 {sub_limit:,}명 이하의 채널에서 조건에 맞는 영상이 없습니다.")

    except HttpError as e:
        error_content = json.loads(e.content.decode())
        error_msg = error_content['error']['message']
        st.error(f"유튜브 API 에러: {error_msg}")
    except Exception as e:
        st.error(f"시스템 에러: {e}")
