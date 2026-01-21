import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import json

# 설정
API_KEY = 'AIzaSyDLY6YYLqiQ_8YXt5eGFUGIFYvzKaOi-Yk'
youtube = build('youtube', 'v3', developerKey=API_KEY)

st.set_page_config(page_title="중소형 떡상 채널 스캐너", layout="wide")
st.title("🎯 1Day ENG: 중소형 채널 벤치마킹 도구")
st.caption("구독자가 적지만 조회수가 폭발 중인 '진짜 고수' 채널을 찾습니다.")

with st.sidebar:
    st.header("⚙️ 필터 설정")
    keyword = st.text_input("검색 키워드", "영어회화 shorts")
    max_results = st.slider("검색 개수", 10, 50, 30)
    
    # 구독자 상한선 설정 (대형 채널 제외)
    sub_limit = st.number_input("구독자 수 상한선 (이하만 표시)", value=100000, step=10000)
    
    # 검색 기간 설정 (최근 영상 위주)
    days_back = st.slider("며칠 이내 영상?", 7, 90, 30)
    published_after = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"

if st.button("신규 트렌드 분석 시작"):
    try:
        with st.spinner('대형 채널을 제외하고 분석 중...'):
            # 1. 최신순/조회수순으로 검색
            search_response = youtube.search().list(
                q=keyword,
                part='snippet',
                maxResults=max_results,
                type='video',
                publishedAfter=published_after, # 최근 영상만
                order='viewCount' # 조회수 높은 순으로 일단 가져옴
            ).execute()

            video_ids = [item['id']['videoId'] for item in search_response['items']]
            channel_ids = [item['snippet']['channelId'] for item in search_response['items']]

            # 2. 영상 및 채널 정보 일괄 호출
            video_response = youtube.videos().list(
                part='statistics,snippet',
                id=','.join(video_ids)
            ).execute()

            channel_response = youtube.channels().list(
                part='statistics',
                id=','.join(list(set(channel_ids)))
            ).execute()

            channel_info = {
                item['id']: {
                    'subs': int(item['statistics'].get('subscriberCount', 1)),
                    'title': item['snippet']['title']
                } for item in channel_response['items']
            }

            video_data = []
            for v in video_response['items']:
                c_id = v['snippet']['channelId']
                sub_count = channel_info.get(c_id, {}).get('subs', 1)
                
                # 설정한 구독자 상한선보다 적은 채널만 포함
                if sub_count <= sub_limit:
                    v_id = v['id']
                    title = v['snippet']['title']
                    view_count = int(v['statistics'].get('viewCount', 0))
                    score = round((view_count / sub_count), 2)
                    
                    video_data.append({
                        "기획 점수": score,
                        "채널명": channel_info.get(c_id, {}).get('title'),
                        "제목": title,
                        "조회수": view_count,
                        "구독자 수": sub_count,
                        "링크": f"https://youtu.be/{v_id}"
                    })

            df = pd.DataFrame(video_data)
            if not df.empty:
                df = df.sort_values(by="기획 점수", ascending=False)
                
                # 가독성을 위해 포맷팅
                display_df = df.copy()
                display_df['조회수'] = display_df['조회수'].apply(lambda x: f"{x:,}")
                display_df['구독자 수'] = display_df['구독자 수'].apply(lambda x: f"{x:,}")
                
                st.dataframe(
                    display_df,
                    column_config={"링크": st.column_config.LinkColumn("영상 링크")},
                    use_container_width=True, hide_index=True
                )
                st.success(f"✅ 구독자 {sub_limit:,}명 이하 채널의 영상 {len(df)}개를 찾았습니다.")
            else:
                st.warning("조건에 맞는 채널이 없습니다. 구독자 상한선을 높이거나 검색어를 바꿔보세요.")

    except HttpError as e:
        st.error(f"API 에러: {json.loads(e.content.decode())['error']['message']}")
