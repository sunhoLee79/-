import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import json
from collections import Counter

# 설정 (API 키는 보안을 위해 환경변수 사용을 권장합니다)
API_KEY = 'AIzaSyDLY6YYLqiQ_8YXt5eGFUGIFYvzKaOi-Yk'
youtube = build('youtube', 'v3', developerKey=API_KEY)

st.set_page_config(page_title="Shorts 머무름 분석기", layout="wide")
st.title("📊 쇼츠 시청 상황 & 주제 분석기")
st.caption("복잡한 설정 없이 키워드만 입력하세요. '머무름 점수'가 높은 영상을 바로 찾아드립니다.")

# 필터를 없애는 대신 내부적으로 최적의 값을 기본 적용합니다.
DEFAULT_DAYS = 14          # 최근 2주일 이내 영상
DEFAULT_SUB_LIMIT = 100000 # 구독자 10만 이하 (중소형 채널)
DEFAULT_MAX_RESULTS = 50   # 최대 50개 분석

# 메인 화면에 검색창만 배치
keyword = st.text_input("분석하고 싶은 주제를 입력하세요", placeholder="예: 캠핑, 요리꿀팁, 자취생, mbti")

if st.button("즉시 분석 시작"):
    if not keyword:
        st.warning("검색어를 입력해 주세요.")
        st.stop()
        
    try:
        published_after = (datetime.utcnow() - timedelta(days=DEFAULT_DAYS)).isoformat() + "Z"
        
        with st.spinner(f"'{keyword}' 관련 고유지율 데이터를 수집 중입니다..."):
            # 1. 쇼츠 위주 검색
            search_response = youtube.search().list(
                q=keyword,
                part='snippet',
                maxResults=DEFAULT_MAX_RESULTS,
                type='video',
                videoDuration='short', 
                publishedAfter=published_after,
                order='viewCount'
            ).execute()

            video_ids = [item['id']['videoId'] for item in search_response['items']]
            channel_ids = [item['snippet']['channelId'] for item in search_response['items']]

            # 2. 영상 상세 통계
            video_response = youtube.videos().list(
                part='statistics,snippet',
                id=','.join(video_ids)
            ).execute()

            # 3. 채널 정보
            channel_response = youtube.channels().list(
                part='statistics,snippet',
                id=','.join(list(set(channel_ids)))
            ).execute()

            channel_info = {item['id']: {
                'subs': int(item['statistics'].get('subscriberCount', 1)),
                'title': item['snippet']['title']
            } for item in channel_response.get('items', [])}

            video_data = []
            all_titles = ""

            for v in video_response.get('items', []):
                stats = v.get('statistics', {})
                snippet = v.get('snippet', {})
                c_id = snippet.get('channelId')
                c_data = channel_info.get(c_id, {'subs': 1, 'title': '알 수 없음'})
                
                # 내부 설정된 구독자 수 제한 적용
                if c_data['subs'] <= DEFAULT_SUB_LIMIT:
                    views = int(stats.get('viewCount', 0))
                    likes = int(stats.get('likeCount', 0))
                    comments = int(stats.get('commentCount', 0))
                    subs = c_data['subs'] if c_data['subs'] > 0 else 1
                    
                    # 기획력 및 머무름 지표 계산
                    planning_score = round(views / subs, 2)
                    engagement_rate = round(((likes + comments) / views) * 100, 2) if views > 0 else 0
                    
                    video_data.append({
                        "머무름 점수": engagement_rate,
                        "기획 점수": planning_score,
                        "제목": snippet.get('title'),
                        "조회수": views,
                        "채널명": c_data['title'],
                        "링크": f"https://youtu.be/{v['id']}"
                    })
                    all_titles += snippet.get('title') + " "

            if video_data:
                df = pd.DataFrame(video_data)
                df = df.sort_values(by="머무름 점수", ascending=False)

                st.subheader("🔝 시청자가 오래 머문 상황 리스트")
                
                display_df = df.copy()
                display_df['조회수'] = display_df['조회수'].apply(lambda x: f"{x:,}")
                
                st.dataframe(
                    display_df,
                    column_config={"링크": st.column_config.LinkColumn("영상 확인")},
                    use_container_width=True,
                    hide_index=True
                )

                # 상황 키워드 분석
                st.divider()
                st.subheader("💡 분석된 영상들의 공통 상황 키워드")
                words = [w for w in all_titles.split() if len(w) > 1]
                top_words = Counter(words).most_common(10)
                
                cols = st.columns(5)
                for i, (word, count) in enumerate(top_words):
                    cols[i%5].metric(f"{i+1}위 키워드", word, f"{count}회 사용")

            else:
                st.warning("분석 결과가 없습니다. 다른 키워드를 입력해 보세요.")

    except Exception as e:
        st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
