import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import platform
from datetime import datetime

# ---------------------------------------------------------
# 0. 페이지 설정 및 한글 폰트 자동 해결
# ---------------------------------------------------------
st.set_page_config(page_title="무릎 매매 스캐너 Pro", layout="centered")

# [중요] 차트 한글 깨짐 해결 (koreanize_matplotlib 사용)
try:
    import koreanize_matplotlib
except ImportError:
    # 라이브러리가 없을 경우를 대비한 폴백(Fallback)
    system_name = platform.system()
    if system_name == 'Windows':
        plt.rc('font', family='Malgun Gothic')
    elif system_name == 'Darwin': # Mac
        plt.rc('font', family='AppleGothic')
    else: # Linux (Streamlit Cloud 등)
        plt.rc('font', family='NanumGothic')

plt.rc('axes', unicode_minus=False)

st.title("🦵 무릎 매매 스캐너 Pro")
st.caption("상승 추세인 우량주가 잠시 쉴 때(눌림목)를 포착합니다.")

# ---------------------------------------------------------
# 1. 데이터 및 한글 종목명 매핑 (대폭 추가)
# ---------------------------------------------------------
SYMBOL_MAP = {
    # 🇺🇸 미국 (빅테크/반도체)
    "AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "GOOGL": "구글(알파벳)", 
    "AMZN": "아마존", "META": "메타(페이스북)", "TSLA": "테슬라", "NFLX": "넷플릭스",
    "AMD": "AMD", "INTC": "인텔", "QCOM": "퀄컴", "AVGO": "브로드컴", "ARM": "ARM",
    "TSM": "TSMC", "MU": "마이크론", "ASML": "ASML", "PLTR": "팔란티어", "COIN": "코인베이스",
    
    # 🇺🇸 미국 (우량주/배당/소비재)
    "JPM": "JP모건", "V": "비자", "MA": "마스터카드", "BAC": "뱅크오브아메리카",
    "LLY": "일라이릴리", "NVO": "노보노디스크", "JNJ": "존슨앤존슨", "PFE": "화이자",
    "WMT": "월마트", "COST": "코스트코", "KO": "코카콜라", "PEP": "펩시코",
    "MCD": "맥도날드", "DIS": "디즈니", "SBUX": "스타벅스", "O": "리얼티인컴",
    
    # 🇰🇷 코스피 (대형주)
    "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "373220.KS": "LG에너지솔루션",
    "207940.KS": "삼성바이오로직스", "005380.KS": "현대차", "000270.KS": "기아",
    "005490.KS": "POSCO홀딩스", "035420.KS": "NAVER", "035720.KS": "카카오",
    "068270.KS": "셀트리온", "051910.KS": "LG화학", "006400.KS": "삼성SDI",
    "105560.KS": "KB금융", "055550.KS": "신한지주", "032830.KS": "삼성생명",
    
    # 🇰🇷 코스닥 (성장주/바이오)
    "247540.KQ": "에코프로비엠", "086520.KQ": "에코프로", "091990.KQ": "셀트리온제약",
    "022100.KQ": "포스코DX", "066970.KQ": "엘앤에프", "196170.KQ": "알테오젠",
    "277810.KQ": "레인보우로보틱스", "293490.KQ": "카카오게임즈", "263750.KQ": "펄어비스"
}

# 시장 그룹 분리 (4개 그룹)
MARKET_GROUPS = {
    "🇺🇸 나스닥 (기술/성장)": "AAPL MSFT NVDA GOOGL AMZN META TSLA AMD NFLX AVGO QCOM PLTR COIN ARM TSM MU",
    "🇺🇸 S&P500 (우량/가치)": "JPM V BAC LLY NVO JNJ WMT COST KO PEP MCD DIS O SBUX",
    "🇰🇷 코스피 (국내대장)": "005930.KS 000660.KS 373220.KS 207940.KS 005380.KS 000270.KS 005490.KS 035420.KS 035720.KS 068270.KS 051910.KS 105560.KS",
    "🇰🇷 코스닥 (변동성大)": "247540.KQ 086520.KQ 196170.KQ 277810.KQ 066970.KQ 091990.KQ 293490.KQ 263750.KQ"
}

def get_korean_name(ticker):
    # 매핑된 이름이 있으면 반환, 없으면 티커 그대로 반환
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
    
    with st.spinner(f"데이터 정밀 분석 중... (대상: {len(tickers)}개)"):
        try:
            data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', threads=True, progress=False, auto_adjust=True)
        except Exception as e:
            st.error(f"데이터 다운로드 실패: {e}")
            return []
    
    results = []
    
    for ticker in tickers:
        try:
            if len(tickers) == 1: df = data
            else: df = data[ticker] if ticker in data.columns.levels[0] else pd.DataFrame()
            
            if df.empty or len(df) < 60: continue
            if df['Close'].isna().all(): continue

            close = df['Close']
            curr_price = float(close.iloc[-1])
            
            ma20 = close.rolling(20).mean() # 생명선
            ma60 = close.rolling(60).mean() # 추세선
            
            curr_ma20 = float(ma20.iloc[-1])
            curr_ma60 = float(ma60.iloc[-1])
            prev_ma20 = float(ma20.iloc[-2])
            
            # 이격도 (현재가와 20일선 차이 %)
            disparity = ((curr_price - curr_ma20) / curr_ma20) * 100
            
            score = 0
            
            # 1. 추세 (정배열)
            if curr_ma20 > curr_ma60: 
                score += 30
                if curr_ma20 > prev_ma20: score += 10
            else:
                score -= 20
            
            # 2. 위치 (무릎 확인)
            if curr_price >= curr_ma20:
                if disparity <= 3.0: score += 40      # 베스트: 20일선 딱 붙음
                elif disparity <= 5.0: score += 25    # 굿: 약간 위
                else: score += 5                      # 쏘쏘: 너무 떴음
            else:
                score -= 30 # 이탈 (위험)

            # 3. 보조지표
            rsi = calculate_rsi(close).iloc[-1]
            if 40 <= rsi <= 60: score += 20
            elif rsi < 30: score += 10

            if score >= 80:
                rec_text = "🦵 최적의 무릎"
                rec_bg = "#d4edda"; rec_color = "#155724"
            elif score >= 50:
                rec_text = "🤔 매수 고려"
                rec_bg = "#fff3cd"; rec_color = "#856404"
            else:
                rec_text = "❌ 관망/매도"
                rec_bg = "#f8d7da"; rec_color = "#721c24"

            # 가격 표시
            is_us = not (".KS" in ticker or ".KQ" in ticker)
            if is_us:
                price_str = f"${curr_price:,.2f}"
                krw_price = f"{curr_price * exchange_rate:,.0f}원"
            else:
                price_str = f"{curr_price:,.0f}원"
                krw_price = "KRW"

            results.append({
                'ticker': ticker,
                'name': get_korean_name(ticker),
                'score': score,
                'rec_text': rec_text, 'rec_bg': rec_bg, 'rec_color': rec_color,
                'price': price_str, 'krw': krw_price,
                'disparity': disparity,
                'ma20': curr_ma20,
                'df': df
            })
            
        except Exception as e:
            continue

    results.sort(key=lambda x: x['score'], reverse=True)
    return results

# ---------------------------------------------------------
# 3. 백테스팅 (수익률 검증)
# ---------------------------------------------------------
def run_knee_backtest(ticker, period="1y"):
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty or len(df) < 60: return None
        
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        balance = 1000000 
        shares = 0
        in_position = False
        buy_price = 0
        trade_log = []
        equity_curve = []
        
        for i in range(60, len(df)):
            date = df.index[i]
            row = df.iloc[i]
            
            curr_equity = balance + (shares * row['Close'])
            equity_curve.append({'Date': date, 'Equity': curr_equity})
            
            # 매도: 20일선 이탈
            if in_position:
                if row['Close'] < row['MA20']:
                    sell_price = row['Close']
                    yield_rate = ((sell_price - buy_price) / buy_price) * 100
                    type_str = '🟢익절' if yield_rate > 0 else '🔴손절'
                    balance += shares * sell_price
                    shares = 0; in_position = False
                    trade_log.append({'구분': type_str, '날짜': date.strftime('%Y-%m-%d'), '수익률': f"{yield_rate:.2f}%"})

            # 매수: 정배열 + 지지 + 눌림목(3%)
            if not in_position:
                cond_trend = row['MA20'] > row['MA60']
                cond_support = row['Close'] >= row['MA20']
                cond_knee = row['Close'] <= (row['MA20'] * 1.03) 
                
                if cond_trend and cond_support and cond_knee:
                    buy_price = row['Close']
                    shares = balance / buy_price
                    balance = 0; in_position = True
                    trade_log.append({'구분': '🚀매수', '날짜': date.strftime('%Y-%m-%d'), '수익률': '-'})

        final_equity = shares * df['Close'].iloc[-1] if in_position else balance
        total_return = ((final_equity - 1000000) / 1000000) * 100
        wins = [t for t in trade_log if '익절' in t['구분']]
        losses = [t for t in trade_log if '손절' in t['구분']]
        win_rate = (len(wins) / (len(wins) + len(losses)) * 100) if (wins or losses) else 0
        
        return {
            'Total': total_return, 'Win_Rate': win_rate, 'Trade_Count': len(wins)+len(losses),
            'Log': trade_log, 'Equity': pd.DataFrame(equity_curve).set_index('Date')
        }
    except Exception as e:
        return None

# ---------------------------------------------------------
# 4. UI 구성 (시장 분리 및 결과 표시)
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🦵 무릎 발굴", "🧪 수익률 검증"])

with tab1:
    st.subheader("🔍 실시간 무릎(눌림목) 스캐너")
    
    # 시장 그룹 선택 (4개로 분리됨)
    group_key = st.selectbox("분석할 시장을 선택하세요:", list(MARKET_GROUPS.keys()))
    
    if 'knee_results' not in st.session_state:
        st.session_state['knee_results'] = []
        
    if st.button("🚀 종목 스캔 시작", type="primary"):
        st.session_state['knee_results'] = analyze_knee_strategy(MARKET_GROUPS[group_key])
        
    if st.session_state['knee_results']:
        results = st.session_state['knee_results']
        if not results:
            st.warning("데이터를 가져오지 못했거나 조건에 맞는 종목이 없습니다.")
        
        for item in results:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    # 이름(티커) 표시
                    st.markdown(f"### {item['name']}")
                    st.caption(item['ticker'])
                with c2:
                    st.markdown(f"#### {item['price']}")
                    if item['krw'] != "KRW": st.caption(f"({item['krw']})")
                with c3:
                    st.markdown(f"""<div style="background-color:{item['rec_bg']}; color:{item['rec_color']}; padding:8px; border-radius:5px; text-align:center; font-weight:bold;">{item['rec_text']}</div>""", unsafe_allow_html=True)
                
                # 차트
                df = item['df'][-90:] # 최근 3달
                if not df.empty:
                    fig, ax = plt.subplots(figsize=(8, 2))
                    ax.plot(df.index, df['Close'], label='주가', color='black', alpha=0.7)
                    ax.plot(df.index, df['Close'].rolling(20).mean()[-90:], label='20일선(생명선)', color='green', lw=2)
                    
                    # 한글 깨짐 방지 테스트용 제목
                    ax.set_title(f"{item['name']} - 20일선 추세", fontsize=10)
                    ax.legend(loc='upper left', fontsize='small')
                    
                    # 차트 스타일링
                    ax.set_xticks([])
                    ax.set_yticks([])
                    for sp in ax.spines.values(): sp.set_visible(False)
                    st.pyplot(fig)
                    plt.close(fig)

with tab2:
    st.subheader("🧪 전략 수익률 검증")
    
    if st.session_state['knee_results']:
        # 검색된 종목으로 목록 채우기
        opts = {f"{r['name']} ({r['ticker']})": r['ticker'] for r in st.session_state['knee_results']}
        sel = st.selectbox("종목 선택:", list(opts.keys()))
        
        if st.button("📊 1년 시뮬레이션 돌리기"):
            ticker = opts[sel]
            with st.spinner("과거 데이터로 매매 중..."):
                res = run_knee_backtest(ticker)
                
            if res:
                col1, col2, col3 = st.columns(3)
                col1.metric("총 수익률", f"{res['Total']:.1f}%", delta_color="normal")
                col2.metric("승률", f"{res['Win_Rate']:.1f}%")
                col3.metric("매매 횟수", f"{res['Trade_Count']}회")
                
                st.line_chart(res['Equity'])
                
                with st.expander("📝 상세 매매 일지"):
                    st.dataframe(pd.DataFrame(res['Log']), use_container_width=True)
    else:
        st.info("👈 먼저 [무릎 발굴] 탭에서 종목을 검색해주세요.")
