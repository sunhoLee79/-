import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import json
from collections import Counter

# 설정
API_KEY = 'AIzaSyDLY6YYLqiQ_8YXt5eGFUGIFYvzKaOi-Yk' # 본인의 API 키로 교체 권장
youtube = build('youtube', 'v3', developerKey=API_KEY)

st.set_page_config(page_title="Shorts 머무름 분석기", layout="wide")
st.title("📊 쇼츠 시청 상황 & 주제 분석기")
st.caption("시청자가 끝까지 머물러 '반응'을 남긴 고효율 쇼츠를 분석합니다.")

with st.sidebar:
    st.header("⚙️ 분석 필터")
    keyword = st.text_input("분석할 주제 키워드", "shorts")
    days_back = st.slider("최근 며칠 이내?", 1, 60, 14)
    sub_limit = st.number_input("채널 규모 상한 (구독자)", value=50000)
    max_results = st.slider("수집 데이터 양", 10, 50, 30)
    published_after = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"

if st.button("시청 머무름 데이터 분석 시작"):
    try:
        with st.spinner('고유지율 예상 영상을 추출 중입니다...'):
            # 1. 쇼츠 위주 검색 (videoDuration='short'는 4분 미만이나 보통 쇼츠가 잡힘)
            search_response = youtube.search().list(
                q=keyword,
                part='snippet',
                maxResults=max_results,
                type='video',
                videoDuration='short', 
                publishedAfter=published_after,
                order='viewCount'
            ).execute()

            video_ids = [item['id']['videoId'] for item in search_response['items']]
            channel_ids = [item['snippet']['channelId'] for item in search_response['items']]

            # 2. 영상 상세 통계 (좋아요, 댓글 포함)
            video_response = youtube.videos().list(
                part='statistics,snippet,contentDetails',
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
                # 진짜 쇼츠(60초 이하)만 필터링 로직 (ISO 8601 duration 분석은 생략, API 기본값 활용)
                stats = v.get('statistics', {})
                snippet = v.get('snippet', {})
                c_id = snippet.get('channelId')
                c_data = channel_info.get(c_id, {'subs': 1, 'title': '알 수 없음'})
                
                if c_data['subs'] <= sub_limit:
                    views = int(stats.get('viewCount', 0))
                    likes = int(stats.get('likeCount', 0))
                    comments = int(stats.get('commentCount', 0))
                    subs = c_data['subs'] if c_data['subs'] > 0 else 1
                    
                    # 지표 계산
                    # 1. 기획력(조회수/구독자): 얼마나 외부 노출이 잘 되었는가
                    planning_score = round(views / subs, 2)
                    # 2. 머무름 지표(상호작용/조회수): 얼마나 끝까지 보고 반응했는가
                    engagement_rate = round(((likes + comments) / views) * 100, 2) if views > 0 else 0
                    
                    video_data.append({
                        "머무름 점수": engagement_rate,
                        "기획 점수": planning_score,
                        "제목": snippet.get('title'),
                        "조회수": views,
                        "좋아요": likes,
                        "채널명": c_data['title'],
                        "링크": f"https://youtu.be/{v['id']}"
                    })
                    all_titles += snippet.get('title') + " "

            if video_data:
                df = pd.DataFrame(video_data)
                # 머무름 점수(Engagement) 순으로 정렬
                df = df.sort_values(by="머무름 점수", ascending=False)

                # 결과 출력
                st.subheader("🔝 끝까지 보게 만든 '상황' 리스트 (머무름 점수 순)")
                st.write("※ 머무름 점수: 조회수 대비 좋아요와 댓글의 비중 (높을수록 몰입도가 높음)")
                
                display_df = df.copy()
                display_df['조회수'] = display_df['조회수'].apply(lambda x: f"{x:,}")
                st.dataframe(
                    display_df,
                    column_config={"링크": st.column_config.LinkColumn("영상 확인")},
                    use_container_width=True,
                    hide_index=True
                )

                # 상황 키워드 분석 (간이)
                st.divider()
                st.subheader("💡 이 영상들이 공통적으로 사용한 '상황' 키워드")
                words = [w for w in all_titles.split() if len(w) > 1]
                top_words = Counter(words).most_common(10)
                
                cols = st.columns(5)
                for i, (word, count) in enumerate(top_words):
                    cols[i%5].metric(f"순위 {i+1}", word, f"{count}회 언급")

            else:
                st.warning("분석 조건에 맞는 영상이 없습니다.")

    except Exception as e:
        st.error(f"오류 발생: {e}")
