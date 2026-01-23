import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import json
from collections import Counter
import re

# 설정
API_KEY = 'AIzaSyDLY6YYLqiQ_8YXt5eGFUGIFYvzKaOi-Yk'
youtube = build('youtube', 'v3', developerKey=API_KEY)

st.set_page_config(page_title="Shorts 주제 분석기", layout="wide")
st.title("🎯 쇼츠 떡상 상황 분석 도구")
st.caption("어떤 상황에서 사람들이 나가지 않고 끝까지 머물렀는지 분석합니다.")

# 내부 기본 설정값
DEFAULT_DAYS = 14
DEFAULT_SUB_LIMIT = 100000
DEFAULT_MAX_RESULTS = 50

# 상단 검색 바
keyword = st.text_input("분석하고 싶은 검색어를 입력하세요", placeholder="예: 일상 브이로그, 요리 꿀팁, 공감 상황극")

if st.button("데이터 분석 시작"):
    if not keyword:
        st.warning("검색어를 입력해 주세요.")
        st.stop()
        
    try:
        published_after = (datetime.utcnow() - timedelta(days=DEFAULT_DAYS)).isoformat() + "Z"
        
        with st.spinner(f"'{keyword}' 주제의 고유지율 데이터를 수집하고 분석하는 중..."):
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
            words_list = []

            for v in video_response.get('items', []):
                stats = v.get('statistics', {})
                snippet = v.get('snippet', {})
                c_id = snippet.get('channelId')
                c_data = channel_info.get(c_id, {'subs': 1, 'title': '알 수 없음'})
                
                if c_data['subs'] <= DEFAULT_SUB_LIMIT:
                    views = int(stats.get('viewCount', 0))
                    likes = int(stats.get('likeCount', 0))
                    comments = int(stats.get('commentCount', 0))
                    subs = c_data['subs'] if c_data['subs'] > 0 else 1
                    
                    planning_score = round(views / subs, 2)
                    engagement_rate = round(((likes + comments) / views) * 100, 2) if views > 0 else 0
                    
                    title = snippet.get('title')
                    video_data.append({
                        "머무름 점수": engagement_rate,
                        "기획 점수": planning_score,
                        "제목": title,
                        "조회수": views,
                        "채널명": c_data['title'],
                        "링크": f"https://youtu.be/{v['id']}"
                    })
                    # 키워드 추출용 (조사 등 제외하고 2글자 이상만)
                    clean_title = re.sub(r'[^\w\s]', '', title)
                    words_list.extend([w for w in clean_title.split() if len(w) > 1])

            if video_data:
                # 탭 구성: 데이터와 분석을 분리
                tab1, tab2 = st.tabs(["📑 분석 영상 리스트", "🔍 주제 및 상황 집중 분석"])

                with tab1:
                    st.subheader("데이터 기반 고유지율 영상")
                    df = pd.DataFrame(video_data).sort_values(by="머무름 점수", ascending=False)
                    display_df = df.copy()
                    display_df['조회수'] = display_df['조회수'].apply(lambda x: f"{x:,}")
                    st.dataframe(
                        display_df,
                        column_config={"링크": st.column_config.LinkColumn("영상 확인")},
                        use_container_width=True,
                        hide_index=True
                    )

                with tab2:
                    st.subheader("💡 시청자가 머무른 '상황' 키워드 TOP 10")
                    top_words = Counter(words_list).most_common(10)
                    
                    # 지표 시각화
                    cols = st.columns(5)
                    for i, (word, count) in enumerate(top_words):
                        cols[i%5].metric(f"{i+1}위 키워드", word, f"{count}번 포착")
                    
                    st.divider()
                    st.markdown("""
                    ### 🧐 어떻게 해석하나요?
                    1. **상황 키워드**: 위 키워드들은 시청자가 끝까지 보고 반응한 영상 제목에 공통적으로 포함된 단어입니다. 
                    2. **머무름의 비밀**: '왜', '방법', '결국', '실제' 같은 단어가 많다면 **서사적 궁금증**을 유발한 것이고, 특정 대상(예: '자취생', '직장인')이 많다면 **공감대** 형성에 성공한 상황입니다.
                    """)

            else:
                st.warning("조건에 맞는 영상이 없습니다.")

    except Exception as e:
        st.error(f"오류 발생: {e}")
