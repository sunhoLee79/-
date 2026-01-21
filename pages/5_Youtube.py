import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from googleapiclient.errors import HttpError
import json

# 1. 설정 (보내주신 API 키 적용)
API_KEY = 'AIzaSyDLY6YYLqiQ_8YXt5eGFUGIFYvzKaOi-Yk'
youtube = build('youtube', 'v3', developerKey=API_KEY)

st.set_page_config(page_title="유튜브 떡상 스캐너", layout="wide")
st.title("🚀 1Day ENG: 인기 콘텐츠 벤치마킹 스캐너")
st.caption("작은 채널에서 조회수가 폭발한 영상을 찾아 기획 의도를 분석합니다.")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    keyword = st.text_input("검색 키워드", "English Shorts")
    max_results = st.slider("검색 개수", 10, 50, 20)
    st.info("기획 점수 = 조회수 / 구독자 수\n1.0 이상이면 성과가 좋은 영상입니다.")

if st.button("분석 시작"):
    try:
        with st.spinner('유튜브 데이터를 정밀 분석 중입니다...'):
            # 1. 검색 API 호출
            search_response = youtube.search().list(
                q=keyword,
                part='snippet',
                maxResults=max_results,
                type='video',
                regionCode='KR'
            ).execute()

            video_ids = [item['id']['videoId'] for item in search_response['items']]
            channel_ids = [item['snippet']['channelId'] for item in search_response['items']]

            # 2. 영상 통계 정보 한 번에 가져오기 (할당량 절약)
            video_response = youtube.videos().list(
                part='statistics,snippet',
                id=','.join(video_ids)
            ).execute()

            # 3. 채널 정보(구독자 수) 한 번에 가져오기
            channel_response = youtube.channels().list(
                part='statistics',
                id=','.join(list(set(channel_ids))) # 중복 채널 제거
            ).execute()

            # 채널 구독자 수 매핑 딕셔너리 생성
            channel_subs = {item['id']: int(item['statistics'].get('subscriberCount', 1)) for item in channel_response['items']}

            video_data = []
            for v in video_response['items']:
                v_id = v['id']
                c_id = v['snippet']['channelId']
                title = v['snippet']['title']
                view_count = int(v['statistics'].get('viewCount', 0))
                sub_count = channel_subs.get(c_id, 1)
                
                # 기획 점수 계산
                score = round((view_count / sub_count), 2)
                
                video_data.append({
                    "기획 점수": score,
                    "제목": title,
                    "조회수": f"{view_count:,}",
                    "구독자 수": f"{sub_count:,}",
                    "링크": f"https://youtu.be/{v_id}"
                })

            # 데이터프레임 출력
            df = pd.DataFrame(video_data)
            if not df.empty:
                # 점수 높은 순 정렬
                df = df.sort_values(by="기획 점수", ascending=False)
                
                # 테이블 출력
                st.dataframe(
                    df, 
                    column_config={
                        "링크": st.column_config.LinkColumn("영상 링크")
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                st.success(f"✅ 분석 완료! 총 {len(df)}개의 영상을 분석했습니다.")
            else:
                st.warning("검색 결과가 없습니다.")

    except HttpError as e:
        error_msg = json.loads(e.content.decode())['error']['message']
        st.error(f"❌ YouTube API 에러: {error_msg}")
        if "quotaExceeded" in error_msg:
            st.warning("오늘 사용할 수 있는 API 할당량을 모두 소진했습니다. 내일 다시 시도해주세요.")
    except Exception as e:
        st.error(f"알 수 없는 오류 발생: {e}")
