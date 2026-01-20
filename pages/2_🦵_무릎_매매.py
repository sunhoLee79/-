import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import platform
from datetime import datetime

# ---------------------------------------------------------
# 0. 페이지 설정
# ---------------------------------------------------------
st.set_page_config(page_title="무릎 매매 스캐너", layout="centered")

# 폰트 설정 (한글 깨짐 방지)
system_name = platform.system()
if system_name == 'Windows':
    plt.rc('font', family='Malgun Gothic')
elif system_name == 'Darwin':
    plt.rc('font', family='AppleGothic')
else:
    plt.rc('font', family='NanumGothic')
plt.rc('axes', unicode_minus=False)

st.title("🦵 무릎 매매 스캐너 (Trend Pullback)")
st.caption("상승 추세 중 잠시 쉬어가는 '무릎(눌림목)' 구간을 공략합니다.")

# ---------------------------------------------------------
# 1. 데이터 및 유틸리티
# ---------------------------------------------------------
SYMBOL_MAP = {
    "AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "GOOGL": "구글", 
    "AMZN": "아마존", "META": "메타", "TSLA": "테슬라", "NFLX": "넷플릭스",
    "AMD": "AMD", "INTC": "인텔", "QCOM": "퀄컴", "AVGO": "브로드컴", 
    "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "373220.KS": "LG에너지솔루션",
    "207940.KS": "삼성바이오", "005380.KS": "현대차", "000270.KS": "기아",
    "005490.KS": "POSCO홀딩스", "035420.KS": "NAVER", "035720.KS": "카카오"
}

MARKET_GROUPS = {
    "🇺🇸 나스닥/S&P 핵심": "AAPL MSFT NVDA GOOGL AMZN META TSLA AMD NFLX AVGO QCOM PLTR COIN JPM V LLY",
    "🇰🇷 코스피/코스닥 대장": "005930.KS 000660.KS 373220.KS 207940.KS 005380.KS 000270.KS 005490.KS 035420.KS 035720.KS 042700.KS 086520.KQ 247540.KQ"
}

def get_korean_name(ticker):
    return SYMBOL_MAP.get(ticker, ticker)

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        df = yf.download("KRW=X", period="1d", progress=False)
        if not df.empty:
            return float(df['Close'].iloc[-1])
        return 1450.0
    except: return 1450.0

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ---------------------------------------------------------
# 2. [핵심] 무릎 매매 분석 로직
# ---------------------------------------------------------
def analyze_knee_strategy(ticker_string):
    tickers = ticker_string.split()
    exchange_rate = get_exchange_rate()
    
    # [수정] 무한 로딩 방지를 위해 auto_adjust=True, threads=False 시도
    with st.spinner(f"데이터 정밀 분석 중... (대상: {len(tickers)}개)"):
        try:
            # period='1y'로 변경 (이동평균선 계산 안정성 확보)
            data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', threads=True, progress=False, auto_adjust=True)
        except Exception as e:
            st.error(f"데이터 다운로드 실패: {e}")
            return []
    
    results = []
    
    for ticker in tickers:
        try:
            # 데이터 추출 (단일 종목 vs 다중 종목 처리)
            if len(tickers) == 1: df = data
            else: df = data[ticker] if ticker in data.columns.levels[0] else pd.DataFrame()
            
            # 유효성 검사
            if df.empty or len(df) < 60: continue
            if df['Close'].isna().all(): continue

            close = df['Close']
            curr_price = float(close.iloc[-1])
            
            # --- [무릎 매매 지표 계산] ---
            ma20 = close.rolling(20).mean() # 생명선 (지지선)
            ma60 = close.rolling(60).mean() # 수급선 (추세선)
            
            curr_ma20 = float(ma20.iloc[-1])
            curr_ma60 = float(ma60.iloc[-1])
            prev_ma20 = float(ma20.iloc[-2])
            
            # 이격도 (현재가와 20일선 사이의 거리, %)
            disparity = ((curr_price - curr_ma20) / curr_ma20) * 100
            
            # 점수 산정 로직 (100점 만점)
            score = 0
            
            # 1. 추세 점수 (40점): 정배열인가? (20일선 > 60일선)
            if curr_ma20 > curr_ma60: 
                score += 30
                # 20일선이 상승 중인가?
                if curr_ma20 > prev_ma20: score += 10
            else:
                # 역배열이면 무릎 매매 대상 아님 (감점)
                score -= 20
            
            # 2. 위치 점수 (40점): 무릎인가? (20일선 근처)
            # 20일선 위에 있어야 함 (지지)
            if curr_price >= curr_ma20:
                # 20일선에서 3% 이내 (최적의 매수점)
                if disparity <= 3.0: score += 40
                # 20일선에서 5% 이내
                elif disparity <= 5.0: score += 25
                # 너무 높게 떠있음 (어깨/머리 가능성)
                else: score += 5
            else:
                # 20일선 깨짐 (위험)
                score -= 30

            # 3. 보조 점수 (20점): 과매도인가?
            rsi = calculate_rsi(close).iloc[-1]
            if 40 <= rsi <= 60: score += 20 # 안정적인 구간
            elif rsi < 30: score += 10 # 과매도 (반등 기대)
            elif rsi > 70: score -= 10 # 과매수 (조정 위험)

            # 추천 등급
            if score >= 80:
                rec_text = "🦵 최적의 무릎"
                rec_bg = "#d4edda"; rec_color = "#155724" # 초록
            elif score >= 50:
                rec_text = "🤔 매수 고려"
                rec_bg = "#fff3cd"; rec_color = "#856404" # 노랑
            else:
                rec_text = "❌ 관망/매도"
                rec_bg = "#f8d7da"; rec_color = "#721c24" # 빨강

            # 가격 포맷팅
            is_us = not (".KS" in ticker or ".KQ" in ticker)
            if is_us:
                price_str = f"${curr_price:,.2f}"
                krw_price = f"{curr_price * exchange_rate:,.0f}원"
            else:
                price_str = f"{curr_price:,.0f}원"
                krw_price = ""

            results.append({
                'ticker': ticker,
                'name': get_korean_name(ticker),
                'score': score,
                'rec_text': rec_text, 'rec_bg': rec_bg, 'rec_color': rec_color,
                'price': price_str, 'krw': krw_price,
                'disparity': disparity, # 이격도
                'ma20': curr_ma20,
                'df': df
            })
            
        except Exception as e:
            continue

    # 점수 높은 순 정렬
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:10]

# ---------------------------------------------------------
# 3. [검증] 백테스팅 (무릎에 사서 어깨에 팔기)
# ---------------------------------------------------------
def run_knee_backtest(ticker, period="1y"):
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty or len(df) < 60: return None
        
        # 지표 생성
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        balance = 1000000 # 초기 자본 100만원
        shares = 0
        in_position = False
        buy_price = 0
        trade_log = []
        equity_curve = []
        
        # 시뮬레이션
        for i in range(60, len(df)):
            date = df.index[i]
            row = df.iloc[i]
            prev = df.iloc[i-1]
            
            curr_equity = balance + (shares * row['Close'])
            equity_curve.append({'Date': date, 'Equity': curr_equity})
            
            # --- [매도 로직: 어깨] ---
            # 조건: 종가가 20일선을 깨고 내려가면 매도
            if in_position:
                if row['Close'] < row['MA20']:
                    sell_price = row['Close']
                    yield_rate = ((sell_price - buy_price) / buy_price) * 100
                    
                    type_str = '🟢익절' if yield_rate > 0 else '🔴손절'
                    balance += shares * sell_price
                    shares = 0; in_position = False
                    trade_log.append({'구분': type_str, '날짜': date.strftime('%Y-%m-%d'), '수익률': f"{yield_rate:.2f}%"})

            # --- [매수 로직: 무릎] ---
            # 조건 1: 정배열 (MA20 > MA60)
            # 조건 2: 종가가 20일선 위에 있음
            # 조건 3: 20일선과의 이격도가 3% 이내 (눌림목)
            if not in_position:
                cond_trend = row['MA20'] > row['MA60']
                cond_support = row['Close'] >= row['MA20']
                cond_knee = row['Close'] <= (row['MA20'] * 1.03) # 20일선 + 3% 이내
                
                if cond_trend and cond_support and cond_knee:
                    buy_price = row['Close']
                    shares = balance / buy_price
                    balance = 0; in_position = True
                    trade_log.append({'구분': '🚀매수', '날짜': date.strftime('%Y-%m-%d'), '수익률': '-'})

        # 최종 결과 계산
        final_price = df['Close'].iloc[-1]
        if in_position:
            final_equity = shares * final_price
        else:
            final_equity = balance
            
        total_return = ((final_equity - 1000000) / 1000000) * 100
        
        # 승률 계산
        wins = [t for t in trade_log if '익절' in t['구분']]
        losses = [t for t in trade_log if '손절' in t['구분']]
        win_rate = (len(wins) / (len(wins) + len(losses)) * 100) if (wins or losses) else 0
        
        return {
            'Total': total_return,
            'Win_Rate': win_rate,
            'Trade_Count': len(wins) + len(losses),
            'Log': trade_log,
            'Equity': pd.DataFrame(equity_curve).set_index('Date')
        }
    except Exception as e:
        st.error(f"백테스팅 오류: {e}")
        return None

# ---------------------------------------------------------
# 4. UI 구성
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🦵 무릎 발굴", "🧪 수익률 검증"])

# === 탭 1: 무릎 발굴 ===
with tab1:
    st.subheader("실시간 무릎(눌림목) 스캐너")
    group = st.radio("분석할 시장:", list(MARKET_GROUPS.keys()), horizontal=True)
    
    if 'knee_results' not in st.session_state:
        st.session_state['knee_results'] = []
        
    if st.button("🔍 무릎 종목 찾기", type="primary"):
        results = analyze_knee_strategy(MARKET_GROUPS[group])
        st.session_state['knee_results'] = results
        
    # 결과 출력
    if st.session_state['knee_results']:
        for item in st.session_state['knee_results']:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(f"### {item['name']}")
                    st.caption(item['ticker'])
                with c2:
                    st.markdown(f"#### {item['price']}")
                    if item['krw']: st.caption(f"({item['krw']})")
                with c3:
                    st.markdown(f"""<div style="background-color:{item['rec_bg']}; color:{item['rec_color']}; padding:10px; border-radius:10px; text-align:center; font-weight:bold;">{item['rec_text']}<br><span style='font-size:12px'>점수: {item['score']}</span></div>""", unsafe_allow_html=True)
                
                # 차트 그리기 (미니)
                st.write(f"📉 **20일선 이격도:** {item['disparity']:.2f}% (0%에 가까울수록 진짜 무릎)")
                df = item['df'][-60:] # 최근 60일만
                fig, ax = plt.subplots(figsize=(8, 2))
                ax.plot(df.index, df['Close'], label='주가', color='black')
                ax.plot(df.index, df['Close'].rolling(20).mean()[-60:], label='20일선(생명선)', color='green', linewidth=2)
                ax.fill_between(df.index, df['Close'], df['Close'].rolling(20).mean()[-60:], alpha=0.1, color='green')
                ax.legend(loc='upper left', fontsize='small')
                ax.set_xticks([])
                ax.set_yticks([])
                for sp in ax.spines.values(): sp.set_visible(False)
                st.pyplot(fig)
                plt.close(fig)

# === 탭 2: 검증 ===
with tab2:
    st.subheader("무릎 매매 전략 검증")
    st.caption("조건: 상승 추세에서 20일선 터치 시 매수 -> 20일선 이탈 시 매도")
    
    if st.session_state['knee_results']:
        # 검색된 종목 중 선택
        opts = {f"{r['name']} ({r['ticker']})": r['ticker'] for r in st.session_state['knee_results']}
        sel = st.selectbox("검증할 종목 선택:", list(opts.keys()))
        
        if st.button("🧪 시뮬레이션 시작"):
            ticker = opts[sel]
            with st.spinner("과거 1년 데이터로 매매해보는 중..."):
                res = run_knee_backtest(ticker)
                
            if res:
                col1, col2, col3 = st.columns(3)
                col1.metric("총 수익률", f"{res['Total']:.1f}%")
                col2.metric("승률", f"{res['Win_Rate']:.1f}%")
                col3.metric("매매 횟수", f"{res['Trade_Count']}회")
                
                st.line_chart(res['Equity'])
                
                with st.expander("매매 상세 기록 보기"):
                    st.table(pd.DataFrame(res['Log']))
    else:
        st.info("먼저 [무릎 발굴] 탭에서 종목을 검색해주세요.")
