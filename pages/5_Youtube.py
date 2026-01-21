import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import json

# 설정
API_KEY = 'AIzaSyDLY6YYLqiQ_8YXt5eGFUGIFYvzKaOi-Yk'
youtube = build('youtube', 'v3', developerKey=API_KEY)

st.set_page_config(page_title="중소형 떡상 스캐너", layout="wide")
st.title("🎯 1Day ENG: 중소형 채널 벤치마킹 도구")
st.caption("구독자가 적지만 조회수가 터진 영상을 찾아 기획의 힌트를 얻으세요.")

with st.sidebar:
    st.header("⚙️ 필터 설정")
    keyword = st.text_input("검색 키워드", "영어회화 shorts")
    max_results = st.slider("검색 개수", 10, 50, 30)
    
    # 구독자 상한선 (기본 10만 명으로 설정)
    sub_limit = st.number_input("구독자 수 상한선 (이하만 표시)", value=100000, step=10000)
    
    # 검색 기간 (최근 영상일수록 트렌디함)
    days_back = st.slider("며칠 이내 영상?", 7, 90, 30)
    published_after = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"

if st.button("신규 트렌드 분석 시작"):
    try:
        with st.spinner('데이터를 불러오고 분석하는 중입니다...'):
            # 1. 검색 API 호출
            search_response = youtube.search().list(
                q=keyword,
                part='snippet',
                maxResults=max_results,
                type='video',
                publishedAfter=published_after,
                order='viewCount'
            ).execute()

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

            # 채널 정보를 안전하게 딕셔너리로 저장 (get 메서드 활용으로 KeyError 방지)
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
                
                # 채널 정보가 없는 경우 대비
                c_data = channel_info.get(c_id, {'subs': 1, 'title': '알 수 없음'})
                sub_count = c_data['subs']
                
                # 구독자 상한선 필터링
                if sub_count <= sub_limit:
                    v_id = v.get('id')
                    title = snippet.get('title', '제목 없음')
                    view_count = int(stats.get('viewCount', 0))
                    # 기획 점수 (조회수 / 구독자 수)
                    score = round((view_count / sub_count), 2)
                    
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
                df = df.sort_values(by="기획 점수", ascending=False)
                
                # 가독성 포맷팅
                display_df = df.copy()
                display_df['조회수'] = display_df['조회수'].apply(lambda x: f"{x:,}")
                display_df['구독자 수'] = display_df['구독자 수'].apply(lambda x: f"{x:,}")
                
                st.dataframe(
                    display_df,
                    column_config={"링크": st.column_config.LinkColumn("영상 링크")},
                    use_container_width=True, 
                    hide_index=True
                )
                st.success(f"✅ 조건에 맞는 영상 {len(df)}개를 찾았습니다.")
            else:
                st.warning(f"구독자 {sub_limit:,}명 이하의 채널에서 검색된 영상이 없습니다. 설정을 변경해 보세요.")

    except HttpError as e:
        error_msg = json.loads(e.content.decode())['error']['message']
        st.error(f"유튜브 API 에러: {error_msg}")
    except Exception as e:
        st.error(f"시스템 에러: {e}")
