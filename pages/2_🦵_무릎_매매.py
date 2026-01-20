import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 1. 설정 및 UI 초기화
# ---------------------------------------------------------
st.set_page_config(layout="wide", page_title="무릎 매매 발굴기 & 검증기")

st.title("🦵 무릎 매매 스캐너 & 백테스터")
st.markdown("""
**전략 핵심:**
* **매수 (무릎):** 20일 이평선이 상승 중(정배열)이고, 주가가 20일 이평선 부근에 왔을 때 (눌림목)
* **매도 (어깨):** 주가가 20일 이평선을 하향 이탈할 때 (추세 꺾임)
""")

# 사이드바 설정
st.sidebar.header("🔍 검색 옵션")
market_type = st.sidebar.selectbox("시장 선택", ["KOSPI", "KOSDAQ"])
scan_limit = st.sidebar.slider("검색할 상위 종목 수 (속도 고려)", 10, 100, 30)
period_days = st.sidebar.slider("검색 기간 (일)", 100, 730, 365)

# ---------------------------------------------------------
# 2. 데이터 처리 및 전략 함수
# ---------------------------------------------------------
@st.cache_data
def get_stock_list(market):
    """시장별 종목 리스트 가져오기"""
    df = fdr.StockListing(market)
    return df.head(scan_limit) # 속도를 위해 상위 N개만

def calculate_strategy(df):
    """
    무릎 매매 전략 계산
    - 매수: 20일선 상승 & 주가가 20일선 위 & 20일선과 이격도 5% 이내
    - 매도: 종가가 20일선 아래로 내려갈 때
    """
    df = df.copy()
    
    # 이동평균선 계산
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # 이평선 기울기 (상승 추세 확인용)
    df['MA20_Slope'] = df['MA20'].diff()
    
    # 매매 신호 초기화
    df['Signal'] = 0 # 1: Buy, -1: Sell
    df['Position'] = 0 # 현재 보유 상태
    
    in_position = False
    buy_price = 0
    
    signals = []
    
    # 시뮬레이션 루프 (벡터화보다 명시적 로직 확인을 위해 루프 사용)
    for i in range(1, len(df)):
        # 데이터가 충분하지 않으면 패스
        if pd.isna(df['MA60'].iloc[i]):
            continue
            
        today = df.iloc[i]
        prev = df.iloc[i-1]
        
        # 1. 매수 조건 (무릎)
        # - 정배열: MA20 > MA60
        # - 추세: MA20 기울기가 양수
        # - 눌림목: 종가가 MA20 위에 있지만, MA20 대비 105% 이하 (너무 높지 않음)
        condition_trend = (today['MA20'] > today['MA60']) and (today['MA20_Slope'] > 0)
        condition_pullback = (today['Close'] >= today['MA20']) and (today['Close'] <= today['MA20'] * 1.05)
        
        # 2. 매도 조건 (어깨)
        # - 종가가 20일선 이탈
        condition_sell = today['Close'] < today['MA20']
        
        if not in_position:
            if condition_trend and condition_pullback:
                df.at[df.index[i], 'Signal'] = 1
                in_position = True
                buy_price = today['Close']
        else:
            if condition_sell:
                df.at[df.index[i], 'Signal'] = -1
                in_position = False
                
    return df

def calculate_returns(df):
    """백테스팅 수익률 계산"""
    trades = []
    in_position = False
    buy_date = None
    buy_price = 0
    
    for index, row in df.iterrows():
        if row['Signal'] == 1: # 매수
            in_position = True
            buy_date = index
            buy_price = row['Close']
        elif row['Signal'] == -1 and in_position: # 매도
            in_position = False
            sell_price = row['Close']
            profit_rate = (sell_price - buy_price) / buy_price * 100
            trades.append({
                '매수일': buy_date.strftime('%Y-%m-%d'),
                '매도일': index.strftime('%Y-%m-%d'),
                '매수가': buy_price,
                '매도가': sell_price,
                '수익률': profit_rate
            })
            
    return pd.DataFrame(trades)

# ---------------------------------------------------------
# 3. 메인 로직 실행
# ---------------------------------------------------------
if st.button("🚀 무릎 매매 종목 발굴 및 검증 시작"):
    st.info(f"{market_type} 시가총액 상위 {scan_limit}개 종목을 분석 중입니다... (시간이 조금 걸립니다)")
    
    stock_list = get_stock_list(market_type)
    results = []
    
    progress_bar = st.progress(0)
    
    for i, (idx, row) in enumerate(stock_list.iterrows()):
        ticker = row['Code']
        name = row['Name']
        
        # 데이터 수집
        try:
            start_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
            df = fdr.DataReader(ticker, start_date)
            
            if len(df) < 60: continue # 데이터 부족 시 패스

            # 전략 적용
            df_strategy = calculate_strategy(df)
            trade_log = calculate_returns(df_strategy)
            
            # 현재 상태 확인 (지금 사야 하는지?)
            last_row = df_strategy.iloc[-1]
            is_buy_signal = last_row['Signal'] == 1
            
            # 통계 집계
            if not trade_log.empty:
                total_return = trade_log['수익률'].sum()
                win_rate = len(trade_log[trade_log['수익률'] > 0]) / len(trade_log) * 100
                trade_count = len(trade_log)
            else:
                total_return = 0
                win_rate = 0
                trade_count = 0
                
            results.append({
                '코드': ticker,
                '종목명': name,
                '현재가': last_row['Close'],
                '총매매횟수': trade_count,
                '승률(%)': round(win_rate, 1),
                '누적수익률(%)': round(total_return, 1),
                '현재신호': "🟢 매수포착" if is_buy_signal else "⚪ 대기",
                '최근데이터': df_strategy # 차트 그리기 위해 저장
            })
            
        except Exception as e:
            continue
            
        progress_bar.progress((i + 1) / len(stock_list))

    # 결과 데이터프레임
    res_df = pd.DataFrame(results)
    
    # ---------------------------------------------------------
    # 4. 결과 디스플레이
    # ---------------------------------------------------------
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("📊 분석 결과 랭킹")
        if not res_df.empty:
            # 수익률 순으로 정렬
            res_df = res_df.sort_values(by='누적수익률(%)', ascending=False)
            
            # 테이블 표시 (보기 좋게 포맷팅)
            display_cols = ['종목명', '현재가', '누적수익률(%)', '승률(%)', '현재신호']
            st.dataframe(
                res_df[display_cols].style.format({
                    '현재가': '{:,.0f}원',
                    '누적수익률(%)': '{:.1f}%',
                    '승률(%)': '{:.1f}%'
                }).background_gradient(subset=['누적수익률(%)'], cmap='RdYlGn'),
                use_container_width=True,
                height=600
            )
        else:
            st.warning("조건에 맞는 종목이 없거나 데이터를 불러올 수 없습니다.")

    with col2:
        st.subheader("📈 상세 차트 및 매매 타점")
        if not res_df.empty:
            selected_ticker = st.selectbox("차트를 볼 종목 선택", res_df['종목명'].values)
            
            # 선택한 종목 데이터 가져오기
            target_data = res_df[res_df['종목명'] == selected_ticker].iloc[0]
            df_chart = target_data['최근데이터']
            trade_history = calculate_returns(df_chart)

            # 차트 그리기 (Plotly)
            fig = go.Figure()

            # 캔들차트
            fig.add_trace(go.Candlestick(x=df_chart.index,
                            open=df_chart['Open'], high=df_chart['High'],
                            low=df_chart['Low'], close=df_chart['Close'],
                            name='주가'))

            # 이평선
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA20'], 
                                     line=dict(color='orange', width=2), name='20일선(생명선)'))
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA60'], 
                                     line=dict(color='gray', width=1), name='60일선(수급선)'))

            # 매수/매도 마커
            buy_signals = df_chart[df_chart['Signal'] == 1]
            sell_signals = df_chart[df_chart['Signal'] == -1]

            fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['Low']*0.98,
                                     mode='markers', marker=dict(symbol='triangle-up', size=12, color='red'),
                                     name='매수(무릎)'))
            
            fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['High']*1.02,
                                     mode='markers', marker=dict(symbol='triangle-down', size=12, color='blue'),
                                     name='매도(어깨)'))

            fig.update_layout(title=f"{selected_ticker} 매매 타점 시뮬레이션", 
                              xaxis_rangeslider_visible=False, height=500)
            st.plotly_chart(fig, use_container_width=True)

            # 상세 매매 내역 표시
            st.write("📝 시뮬레이션 상세 내역 (최근 1년)")
            if not trade_history.empty:
                st.dataframe(trade_history.style.format({
                    '매수가': '{:,.0f}', '매도가': '{:,.0f}', '수익률': '{:.2f}%'
                }))
            else:
                st.write("해당 기간 동안 매매 신호가 발생하지 않았습니다.")
