import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import platform
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 0. 페이지 설정
# ---------------------------------------------------------
st.set_page_config(page_title="AI 주식 전략가 Pro", layout="wide")

# 폰트 설정 (한글 깨짐 방지)
system_name = platform.system()
if system_name == 'Windows':
    plt.rc('font', family='Malgun Gothic')
elif system_name == 'Darwin':
    plt.rc('font', family='AppleGothic')
else:
    plt.rc('font', family='NanumGothic')
plt.rc('axes', unicode_minus=False)

st.title("📱 AI 주식 전략가 (Trend Rider)")
st.caption("실시간 발굴 → AI 미래 예측 → 백테스팅 검증의 3단계 올인원 솔루션")

# ---------------------------------------------------------
# 1. 데이터 및 유틸리티
# ---------------------------------------------------------
SYMBOL_MAP = {
    # 🇺🇸 나스닥 (Big Tech)
    "AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "GOOGL": "구글", 
    "AMZN": "아마존", "META": "메타", "TSLA": "테슬라", "NFLX": "넷플릭스",
    "AMD": "AMD", "INTC": "인텔", "QCOM": "퀄컴", "AVGO": "브로드컴", 
    "TXN": "텍사스인스트루먼트", "ASML": "ASML", "AMGN": "암젠", "CSCO": "시스코", 
    "PEP": "펩시코", "COST": "코스트코", "TMUS": "티모바일", "CMCSA": "컴캐스트", 
    "PLTR": "팔란티어", "HON": "허니웰", "MSTR": "마이크로스트래티지", "COIN": "코인베이스",
    "SHOP": "쇼피파이", "NOW": "서비스나우", "ISRG": "인튜이티브서지컬",
    
    # 🇺🇸 S&P 500 (우량주)
    "BRK-B": "버크셔해서웨이", "JPM": "JP모건", "JNJ": "존슨앤존슨", "V": "비자",
    "PG": "P&G", "XOM": "엑손모빌", "HD": "홈디포", "UNH": "유나이티드헬스",
    "CVX": "셰브론", "MRK": "머크", "ABBV": "애브비", "KO": "코카콜라",
    "BAC": "뱅크오브아메리카", "WMT": "월마트", "MCD": "맥도날드", "DIS": "디즈니",
    "PFE": "화이자", "T": "AT&T", "VZ": "버라이즌", "NEE": "넥스트에라",
    "PM": "필립모리스", "NKE": "나이키", "O": "리얼티인컴", "LMT": "록히드마틴",
    
    # 🇰🇷 한국
    "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "373220.KS": "LG에너지솔루션",
    "207940.KS": "삼성바이오", "005380.KS": "현대차", "000270.KS": "기아",
    "005490.KS": "POSCO홀딩스", "035420.KS": "NAVER", "035720.KS": "카카오",
    "051910.KS": "LG화학", "006400.KS": "삼성SDI", "105560.KS": "KB금융",
    "055550.KS": "신한지주", "003550.KS": "LG",
    "247540.KQ": "에코프로비엠", "086520.KQ": "에코프로", "091990.KQ": "셀트리온제약",
    "022100.KQ": "포스코DX", "066970.KQ": "엘앤에프", "293490.KQ": "카카오게임즈"
}

MARKET_GROUPS = {
    "🇺🇸 나스닥 (기술주)": "AAPL MSFT NVDA GOOGL AMZN META TSLA AVGO COST PEP AMD NFLX INTC QCOM PLTR ASML AMGN CSCO TXN HON MSTR COIN SHOP NOW",
    "🇺🇸 S&P 500 (우량주)": "BRK-B JPM JNJ V PG XOM HD UNH CVX MRK ABBV KO PEP BAC WMT MCD DIS PFE T VZ NEE PM NKE O LMT ISRG",
    "🇰🇷 코스피 200": "005930.KS 000660.KS 373220.KS 207940.KS 005380.KS 000270.KS 005490.KS 035420.KS 035720.KS 051910.KS 006400.KS 105560.KS 055550.KS 003550.KS",
    "🇰🇷 코스닥 150": "247540.KQ 086520.KQ 091990.KQ 022100.KQ 066970.KQ 293490.KQ 035900.KQ 041960.KQ 278280.KQ 214150.KQ"
}

def get_korean_name(ticker):
    return SYMBOL_MAP.get(ticker, ticker)

def get_stock_link(ticker):
    if ".KS" in ticker or ".KQ" in ticker:
        code = ticker.split('.')[0]
        return f"https://finance.naver.com/item/main.naver?code={code}"
    else:
        return f"https://finance.yahoo.com/quote/{ticker}"

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        return float(yf.download("KRW=X", period="1d", progress=False)['Close'].iloc[-1])
    except: return 1450.0

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ---------------------------------------------------------
# 2. [기능 1] 실시간 스캐너 (기존 로직 유지)
# ---------------------------------------------------------
def analyze_realtime(ticker_string):
    tickers = ticker_string.split()
    exchange_rate = get_exchange_rate()
    
    with st.spinner(f"실시간 데이터 분석 중... (환율: {exchange_rate:.0f}원)"):
        try:
            data = yf.download(tickers, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False)
        except: return [], exchange_rate
    
    results = []
    
    for ticker in tickers:
        try:
            if len(tickers) == 1: df = data
            else: df = data[ticker]
            
            if df.empty or len(df) < 60: continue
            
            close = df['Close']
            curr_price = close.iloc[-1]
            
            # 지표 계산
            ma5 = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean()
            bb_up = ma20 + (close.rolling(20).std() * 2)
            rsi = calculate_rsi(close).iloc[-1]
            vol_mean = df['Volume'].rolling(20).mean().iloc[-1]
            vol_ratio = (df['Volume'].iloc[-1] / vol_mean) if vol_mean > 0 else 0
            
            # 점수 산정
            score = 0
            if ma5.iloc[-1] > ma20.iloc[-1] and ma20.iloc[-1] > ma60.iloc[-1]: score += 30 # 정배열
            
            dist = (curr_price - bb_up.iloc[-1]) / bb_up.iloc[-1]
            is_breakout = False
            if dist >= 0: score += 30; is_breakout = True # 돌파
            elif dist >= -0.02: score += 15
            
            if vol_ratio >= 1.5: score += 20 # 거래량
            elif vol_ratio >= 1.2: score += 10
            
            if rsi >= 50: score += 20 # 추세 강도

            # 추천 멘트
            if score >= 80:
                rec_text = "🔥 강력매수 (추세추종)"
                rec_bg = "#d4edda"; rec_color = "#155724"
            elif score >= 50:
                rec_text = "✅ 매수관점"
                rec_bg = "#cce5ff"; rec_color = "#004085"
            else:
                rec_text = "👀 관망필요"
                rec_bg = "#f8d7da"; rec_color = "#721c24"

            # 가격 표시
            is_us = not (".KS" in ticker or ".KQ" in ticker)
            if is_us:
                krw_val = curr_price * exchange_rate
                price_main = f"${curr_price:,.2f}"
                price_sub = f"(약 {krw_val:,.0f}원)"
                table_price = f"₩{krw_val:,.0f}"
                stop_str = f"${ma20.iloc[-1]:,.2f}"
            else:
                price_main = f"₩{curr_price:,.0f}"
                price_sub = ""
                table_price = f"₩{curr_price:,.0f}"
                stop_str = f"₩{ma20.iloc[-1]:,.0f}"

            results.append({
                'ticker': ticker,
                'name': get_korean_name(ticker),
                'link': get_stock_link(ticker),
                'score': score,
                'rec_text': rec_text, 'rec_bg': rec_bg, 'rec_color': rec_color,
                'price_main': price_main, 'price_sub': price_sub, 'table_price': table_price,
                'stop_str': stop_str,
                'change_pct': ((curr_price - close.iloc[-2])/close.iloc[-2])*100,
                'rsi': rsi, 'is_breakout': is_breakout,
                'df': df, 'bb_up': bb_up, 'ma20': ma20
            })
        except: continue

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:10]

# ---------------------------------------------------------
# 3. [기능 2] 심층 분석 (Monte Carlo + Vol Spike) - NEW!
# ---------------------------------------------------------
def run_advanced_analysis(ticker):
    # 데이터 수집 (1년치)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    try:
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if df.empty: return None, None
        
        # MultiIndex 처리 (yfinance 최신버전 대응)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker, axis=1, level=1) if ticker in df.columns.levels[1] else df
            if df.empty: # 구조가 다를 경우 단순화
                 df = yf.download(ticker, start=start_date, end=end_date, progress=False)

    except: return None, None

    # --- A. 기술적 지표 & 거래량 급증 ---
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_60'] = df['Close'].rolling(window=60).mean()
    df['std'] = df['Close'].rolling(window=20).std()
    df['Upper_Band'] = df['SMA_20'] + (df['std'] * 2)
    df['Lower_Band'] = df['SMA_20'] - (df['std'] * 2)

    # 거래량 급증 (2.5배)
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    df['Vol_Spike'] = df['Volume'] > (df['Vol_SMA_20'] * 2.5)

    # --- B. 몬테카를로 시뮬레이션 ---
    daily_returns = df['Close'].pct_change().dropna()
    avg_daily_return = daily_returns.mean()
    daily_volatility = daily_returns.std()

    days_to_predict = 30
    simulation_count = 100
    last_price = df['Close'].iloc[-1]
    
    simulation_df = pd.DataFrame()
    for x in range(simulation_count):
        price_series = [last_price]
        for y in range(days_to_predict):
            shock = np.random.normal(avg_daily_return, daily_volatility)
            price = price_series[-1] * (1 + shock)
            price_series.append(price)
        simulation_df[x] = price_series
    
    simulation_df['Mean_Path'] = simulation_df.mean(axis=1)
    expected_price = simulation_df['Mean_Path'].iloc[-1]
    roi = ((expected_price - last_price) / last_price) * 100

    # --- C. 시각화 (Matplotlib) ---
    fig = plt.figure(figsize=(12, 6))
    gs = gridspec.GridSpec(2, 2, height_ratios=[2, 1])

    # 1. 가격 & 밴드
    ax1 = plt.subplot(gs[0, 0])
    ax1.plot(df.index, df['Close'], label='Price', color='black', alpha=0.7)
    ax1.plot(df.index, df['SMA_20'], label='SMA 20', color='orange', linestyle='--')
    ax1.fill_between(df.index, df['Upper_Band'], df['Lower_Band'], color='gray', alpha=0.1)
    ax1.set_title(f"Price Trend & Bollinger Band ({ticker})")
    ax1.legend(loc='upper left', fontsize='small')
    ax1.grid(True, alpha=0.3)
    ax1.set_xticklabels([])

    # 2. 거래량 (Spike 강조)
    ax2 = plt.subplot(gs[1, 0])
    ax2.bar(df.index, df['Volume'], color='gray', alpha=0.3)
    spike_dates = df[df['Vol_Spike']].index
    spike_vols = df[df['Vol_Spike']]['Volume']
    ax2.bar(spike_dates, spike_vols, color='red', alpha=1.0, label='Spike (>2.5x)')
    ax2.set_title("Volume Spike Detection")
    ax2.legend(loc='upper left', fontsize='small')
    ax2.grid(True, alpha=0.3)

    # 3. 예측 시뮬레이션
    ax3 = plt.subplot(gs[:, 1])
    future_dates = [df.index[-1] + timedelta(days=x) for x in range(days_to_predict + 1)]
    for x in range(simulation_count):
        ax3.plot(future_dates, simulation_df[x], color='green', alpha=0.05)
    
    ax3.plot(future_dates, simulation_df['Mean_Path'], color='red', linewidth=2, label='Expected Avg')
    ax3.axhline(y=last_price, color='black', linestyle=':', label='Current')
    ax3.set_title(f"AI Prediction (Next 30 Days)\nExp: {roi:+.1f}%")
    ax3.legend(loc='upper left', fontsize='small')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    
    # 요약 정보 리턴
    last_vol_spike = "최근 특이사항 없음"
    if not spike_dates.empty:
        days_diff = (end_date - spike_dates[-1]).days
        if days_diff <= 5: 
            last_vol_spike = f"🚨 {days_diff}일 전 '세력 개입(거래량 폭발)' 감지!"
    
    summary = {
        "exp_price": expected_price,
        "roi": roi,
        "vol_alert": last_vol_spike,
        "volatility": daily_volatility * 100
    }
    
    return fig, summary

# ---------------------------------------------------------
# 4. [기능 3] 백테스팅 (기존 로직 유지)
# ---------------------------------------------------------
def run_backtest(ticker):
    try:
        df = yf.download(ticker, period="1y", progress=False)
        if df.empty or len(df) < 60: return None
        if isinstance(df.columns, pd.MultiIndex):
             # Handle MultiIndex for Backtest
             try: df = df.xs(ticker, axis=1, level=1)
             except: pass # If fails, assume single level or handle loosely

        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['Std'] = df['Close'].rolling(20).std()
        df['BB_Up'] = df['MA20'] + (df['Std'] * 2)
        df['Vol_Avg'] = df['Volume'].rolling(20).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        
        balance = 1000000; shares = 0; in_position = False
        buy_price = 0; trade_log = []; equity_curve = []
        
        for i in range(60, len(df)):
            date = df.index[i]; row = df.iloc[i]; prev = df.iloc[i-1]
            curr_equity = balance + (shares * row['Close'])
            equity_curve.append({'Date': date, 'Equity': curr_equity})
            
            if in_position: # 매도 로직
                if row['Close'] < row['MA20']:
                    sell_price = row['Close']
                    ret = ((sell_price - buy_price) / buy_price) * 100
                    type_str = '💰익절' if ret > 0 else '💧손절'
                    balance += shares * sell_price
                    trade_log.append({'Type': type_str, 'Date': date, 'Price': sell_price, 'Return': ret})
                    shares = 0; in_position = False
            else: # 매수 로직
                cond1 = (row['MA5'] > row['MA20']) and (row['MA20'] > row['MA60'])
                cond2 = row['Close'] > row['BB_Up']
                cond3 = (prev['Vol_Avg'] > 0) and (row['Volume'] > prev['Vol_Avg'] * 1.5)
                cond4 = row['RSI'] >= 50
                if cond1 and cond2 and cond3 and cond4:
                    buy_price = row['Close']
                    shares = balance / buy_price
                    balance = 0; in_position = True
                    trade_log.append({'Type': '🚀매수', 'Date': date, 'Price': buy_price, 'Return': 0})

        final_equity = balance + (shares * df['Close'].iloc[-1])
        total_return = ((final_equity - 1000000) / 1000000) * 100
        wins = [t for t in trade_log if '익절' in t['Type']]
        losses = [t for t in trade_log if '손절' in t['Type']]
        win_rate = (len(wins) / (len(wins) + len(losses)) * 100) if (wins or losses) else 0
        
        return {
            'Total': total_return, 'Win_Rate': win_rate, 'Count': len(wins)+len(losses),
            'Log': trade_log, 'Equity': pd.DataFrame(equity_curve).set_index('Date')
        }
    except Exception as e: return None

# ---------------------------------------------------------
# 5. 메인 UI 구성
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 1.실시간 발굴", "🧠 2.심층 분석 & 예측", "🧪 3.백테스팅 검증"])

# =========================================================
# [탭 1] 실시간 발굴 (Scanner)
# =========================================================
with tab1:
    st.subheader("🚀 실시간 급등주 스캐너")
    st.write("현재 시장에서 상승 추세와 거래량이 붙은 종목을 찾아냅니다.")
    
    col_opt, col_btn = st.columns([3, 1])
    with col_opt:
        group = st.radio("시장 선택:", list(MARKET_GROUPS.keys()), horizontal=True)
    with col_btn:
        st.write("") # Spacer
        run_scan = st.button("🔄 스캔 시작", type="primary", use_container_width=True)

    if 'analysis_results' not in st.session_state:
        st.session_state['analysis_results'] = []

    if run_scan:
        top_stocks = analyze_realtime(MARKET_GROUPS[group])
        st.session_state['analysis_results'] = top_stocks
        st.session_state['analysis_time'] = datetime.now().strftime('%m-%d %H:%M')

    if st.session_state['analysis_results']:
        results = st.session_state['analysis_results']
        st.caption(f"🕒 업데이트: {st.session_state.get('analysis_time', '-')}")
        
        # 카드 뷰
        for i, s in enumerate(results):
            with st.container(border=True):
                c1, c2, c3 = st.columns([1.5, 3, 1])
                with c1:
                    st.markdown(f"### #{i+1} {s['name']}")
                    st.caption(s['ticker'])
                    st.markdown(f"**{s['price_main']}**")
                    st.markdown(f"<span style='color:{'red' if s['change_pct']>0 else 'blue'}'>{s['change_pct']:.2f}%</span>", unsafe_allow_html=True)
                
                with c2:
                    st.write(f"**평가 점수: {s['score']}점**")
                    st.progress(s['score']/100)
                    st.caption(f"추천의견: {s['rec_text']} | RSI: {s['rsi']:.0f}")
                    # 미니 차트
                    df = s['df']
                    fig_mini, ax_mini = plt.subplots(figsize=(4, 1))
                    ax_mini.plot(df.index, df['Close'], color='red' if s['change_pct']>0 else 'blue')
                    ax_mini.axis('off')
                    st.pyplot(fig_mini)
                    plt.close(fig_mini)
                    
                with c3:
                    st.write("")
                    st.link_button("네이버/야후", s['link'])

# =========================================================
# [탭 2] 심층 분석 (Deep Dive - New!)
# =========================================================
with tab2:
    st.subheader("🧠 AI 심층 분석 (Monte Carlo + Vol Spike)")
    st.info("실시간 발굴된 종목 중 하나를 선택하여 미래 주가를 시뮬레이션하고 '세력 개입'을 확인하세요.")

    if 'analysis_results' in st.session_state and st.session_state['analysis_results']:
        results = st.session_state['analysis_results']
        options = {f"{s['name']} ({s['ticker']})": s['ticker'] for s in results}
        
        c_sel, c_go = st.columns([3, 1])
        with c_sel:
            selected_key = st.selectbox("분석할 종목 선택:", list(options.keys()))
        with c_go:
            st.write("")
            run_ai = st.button("🔮 AI 예측 실행", type="primary", use_container_width=True)

        if run_ai:
            target_ticker = options[selected_key]
            with st.spinner(f"[{target_ticker}] 몬테카를로 시뮬레이션 가동 중..."):
                fig, summary = run_advanced_analysis(target_ticker)
            
            if fig:
                # 1. 요약 메트릭
                m1, m2, m3 = st.columns(3)
                m1.metric("30일 후 예상가", f"${summary['exp_price']:.2f}", f"{summary['roi']:.2f}%")
                m2.metric("일일 변동성(리스크)", f"{summary['volatility']:.2f}%")
                
                # 2. 거래량 알림
                if "급증" in summary['vol_alert']:
                    st.error(summary['vol_alert'])
                else:
                    st.success("최근 비정상적인 거래량 급증은 없습니다.")

                # 3. 그래프 출력
                st.pyplot(fig)
                st.caption("왼쪽 하단의 빨간색 막대가 '거래량 급증(세력 개입 가능성)' 신호입니다.")
            else:
                st.error("데이터를 불러올 수 없습니다.")
    else:
        st.warning("먼저 [1.실시간 발굴] 탭에서 종목을 스캔해주세요.")

# =========================================================
# [탭 3] 백테스팅 (Backtest)
# =========================================================
with tab3:
    st.subheader("🧪 전략 유효성 검증")
    
    if 'analysis_results' in st.session_state and st.session_state['analysis_results']:
        results = st.session_state['analysis_results']
        options = {f"{s['name']} ({s['ticker']})": s['ticker'] for s in results}
        
        target_key = st.selectbox("검증할 종목 선택:", list(options.keys()), key="bt_select")
        
        if st.button("🧪 1년치 백테스팅 시작"):
            ticker = options[target_key]
            with st.spinner("과거 데이터 시뮬레이션 중..."):
                res = run_backtest(ticker)
            
            if res:
                c1, c2, c3 = st.columns(3)
                c1.metric("총 수익률", f"{res['Total']:.1f}%", delta_color="normal")
                c2.metric("승률", f"{res['Win_Rate']:.0f}%")
                c3.metric("매매 횟수", f"{res['Count']}회")
                
                st.line_chart(res['Equity'])
                with st.expander("매매 상세 로그 확인"):
                    st.dataframe(pd.DataFrame(res['Log']))
            else:
                st.error("백테스팅 데이터 부족")
    else:
        st.warning("먼저 [1.실시간 발굴] 탭에서 종목을 스캔해주세요.")
