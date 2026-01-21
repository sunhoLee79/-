import streamlit as st
from googleapiclient.discovery import build
import pandas as pd

# 1. 설정 (본인의 API 키를 입력하세요)
API_KEY = 'AIzaSyDLY6YYLqiQ_8YXt5eGFUGIFYvzKaOi-Yk'
youtube = build('youtube', 'v3', developerKey=API_KEY)

st.set_page_config(page_title="유튜브 떡상 스캐너", layout="wide")
st.title("🚀 1Day ENG: 인기 콘텐츠 벤치마킹 스캐너")
st.caption("구독자 대비 조회수가 높은 '진짜 인기 영상'을 찾아냅니다.")

# 검색 설정
with st.sidebar:
    keyword = st.text_input("검색 키워드", "영어회화 쇼츠")
    max_results = st.slider("검색 개수", 10, 50, 20)
    order_type = st.selectbox("정렬 기준", ["relevance", "date", "viewCount"])

if st.button("분석 시작"):
    with st.spinner('데이터 분석 중...'):
        # 유튜브 검색 실행
        search_response = youtube.search().list(
            q=keyword,
            part='snippet',
            maxResults=max_results,
            type='video',
            order=order_type
        ).execute()

        video_data = []
        for item in search_response['items']:
            video_id = item['id']['videoId']
            channel_id = item['snippet']['channelId']
            title = item['snippet']['title']
            
            # 영상 상세 정보 (조회수)
            video_stats = youtube.videos().list(
                part='statistics',
                id=video_id
            ).execute()
            
            # 채널 상세 정보 (구독자 수)
            channel_stats = youtube.channels().list(
                part='statistics',
                id=channel_id
            ).execute()

            try:
                view_count = int(video_stats['items'][0]['statistics'].get('viewCount', 0))
                sub_count = int(channel_stats['items'][0]['statistics'].get('subscriberCount', 1)) # 0명 방지
                
                # 기획 점수 계산 (구독자 대비 조회수 비율)
                score = round((view_count / sub_count), 2)
                
                video_data.append({
                    "제목": title,
                    "조회수": view_count,
                    "구독자 수": sub_count,
                    "기획 점수(비율)": score,
                    "링크": f"https://youtu.be/{video_id}"
                })
            except:
                continue

        # 데이터프레임 변환 및 출력
        df = pd.DataFrame(video_data)
        if not df.empty:
            df = df.sort_values(by="기획 점수(비율)", ascending=False)
            st.dataframe(df, use_container_width=True)
            
            st.success("✅ 분석 완료! '기획 점수'가 높은 영상을 먼저 확인하세요.")
        else:
            st.error("결과가 없습니다. API 키나 검색어를 확인해주세요.")
