import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import platform
from datetime import datetime

# ---------------------------------------------------------
# 0. 페이지 설정
# ---------------------------------------------------------
st.set_page_config(page_title="AI 주식 전략가 Pro", layout="centered")

# 폰트 설정
system_name = platform.system()
if system_name == 'Windows':
    plt.rc('font', family='Malgun Gothic')
elif system_name == 'Darwin':
    plt.rc('font', family='AppleGothic')
else:
    plt.rc('font', family='NanumGothic')
plt.rc('axes', unicode_minus=False)

st.title("📱 AI 주식 전략가 (Trend Rider)")
st.caption("실시간 발굴 종목을 즉시 백테스팅으로 검증하세요.")

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
    
    # 🇺🇸 S&P 500 (우량주)
    "BRK-B": "버크셔해서웨이", "JPM": "JP모건", "JNJ": "존슨앤존슨", "V": "비자",
    "PG": "P&G", "XOM": "엑손모빌", "HD": "홈디포", "UNH": "유나이티드헬스",
    "CVX": "셰브론", "MRK": "머크", "ABBV": "애브비", "KO": "코카콜라",
    "BAC": "뱅크오브아메리카", "WMT": "월마트", "MCD": "맥도날드", "DIS": "디즈니",
    "PFE": "화이자", "T": "AT&T", "VZ": "버라이즌", "NEE": "넥스트에라",
    "PM": "필립모리스", "NKE": "나이키", "O": "리얼티인컴",
    
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
    "🇺🇸 나스닥 (기술주)": "AAPL MSFT NVDA GOOGL AMZN META TSLA AVGO COST PEP AMD NFLX INTC QCOM PLTR ASML AMGN CSCO TXN HON MSTR COIN",
    "🇺🇸 S&P 500 (우량주)": "BRK-B JPM JNJ V PG XOM HD UNH CVX MRK ABBV KO PEP BAC WMT MCD DIS PFE T VZ NEE PM NKE O",
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
# 2. [기능 1] 실시간 분석 (수익률 극대화 전략 적용)
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
            ma20 = close.rolling(20).mean() # 생명선
            ma60 = close.rolling(60).mean()
            bb_up = ma20 + (close.rolling(20).std() * 2)
            rsi = calculate_rsi(close).iloc[-1]
            vol_ratio = (df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]) if df['Volume'].rolling(20).mean().iloc[-1] > 0 else 0
            
            # 점수 산정 (수익률 극대화 로직)
            score = 0
            
            # A. 정배열 (Trend)
            if ma5.iloc[-1] > ma20.iloc[-1] and ma20.iloc[-1] > ma60.iloc[-1]: score += 30
            
            # B. 볼린저 돌파 (Momentum)
            dist = (curr_price - bb_up.iloc[-1]) / bb_up.iloc[-1]
            is_breakout = False
            if dist >= 0: 
                score += 30
                is_breakout = True
            elif dist >= -0.02: score += 15
            
            # C. 거래량 (Fuel)
            if vol_ratio >= 1.5: score += 20
            elif vol_ratio >= 1.2: score += 10
            
            # D. RSI (추세 가속도) - 과열이어도 점수 줌 (Trend Riding)
            if rsi >= 50: score += 20 

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

            # 가격 표시 (HTML용)
            is_us = not (".KS" in ticker or ".KQ" in ticker)
            if is_us:
                krw_val = curr_price * exchange_rate
                price_main = f"${curr_price:,.2f}"
                price_sub = f"(약 {krw_val:,.0f}원)"
                table_price = f"₩{krw_val:,.0f}"
                # 목표가는 무한대(추세지속)으로 표시
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
# 3. [기능 2] 백테스팅 (추세 끝까지 먹기)
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def download_data_safe(ticker, period):
    try:
        return yf.download(ticker, period=period, progress=False, timeout=10)
    except: return pd.DataFrame()

def run_backtest(ticker, period="1y"):
    try:
        df = download_data_safe(ticker, period)
        if df.empty or len(df) < 60: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # 지표 생성
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean() # 손절라인
        df['MA60'] = df['Close'].rolling(60).mean()
        df['Std'] = df['Close'].rolling(20).std()
        df['BB_Up'] = df['MA20'] + (df['Std'] * 2)
        df['Vol_Avg'] = df['Volume'].rolling(20).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        
        balance = 1000000
        shares = 0
        in_position = False
        buy_price = 0
        trade_log = []
        equity_curve = []
        
        # 시뮬레이션
        for i in range(60, len(df)):
            date = df.index[i]
            row = df.iloc[i]
            if i == 0: continue
            prev = df.iloc[i-1]
            
            curr_equity = balance + (shares * row['Close'])
            equity_curve.append({'Date': date, 'Equity': curr_equity})
            
            # [매도]: 20일선 깨질 때만 판다 (익절 제한 없음)
            if in_position:
                if row['Close'] < row['MA20']:
                    sell_price = row['Close']
                    ret = ((sell_price - buy_price) / buy_price) * 100
                    
                    type_str = '💰익절(추세끝)' if ret > 0 else '💧손절(이탈)'
                    balance += shares * sell_price
                    trade_log.append({'Type': type_str, 'Date': date, 'Price': sell_price, 'Return': ret})
                    shares = 0; in_position = False

            # [매수]: 정배열 + 돌파 + 수급 (RSI 제한 없음)
            if not in_position:
                cond1 = (row['MA5'] > row['MA20']) and (row['MA20'] > row['MA60'])
                cond2 = row['Close'] > row['BB_Up']
                cond3 = (prev['Vol_Avg'] > 0) and (row['Volume'] > prev['Vol_Avg'] * 1.5)
                cond4 = row['RSI'] >= 50 # 과열도 OK
                
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
    except: return None

# ---------------------------------------------------------
# 4. 메인 UI (탭 구조 + 데이터 연동)
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📊 실시간 발굴", "🧪 수익률 검증"])

# =========================================================
# [탭 1] 실시간 분석
# =========================================================
with tab1:
    st.subheader("🚀 실시간 급등주 스캐너")
    group = st.radio("시장을 선택하세요:", list(MARKET_GROUPS.keys()), horizontal=True)
    
    # 세션 상태 초기화
    if 'analysis_results' not in st.session_state:
        st.session_state['analysis_results'] = []

    if st.button("🔄 분석 실행", type="primary"):
        now = datetime.now()
        
        # 분석 실행
        top_stocks = analyze_realtime(MARKET_GROUPS[group])
        
        # 결과 저장 (탭 2에서 쓰기 위해)
        st.session_state['analysis_results'] = top_stocks
        st.session_state['analysis_time'] = now.strftime('%m-%d %H:%M')

    # 결과가 있으면 출력 (버튼 안 눌러도 유지됨)
    if st.session_state['analysis_results']:
        results = st.session_state['analysis_results']
        st.caption(f"🕒 기준: {st.session_state.get('analysis_time', '-')}")
        
        # [A] 요약 표
        summary = []
        for i, s in enumerate(results):
            summary.append({
                "순위": i+1, "종목명": s['name'], "현재가": s['table_price'],
                "추천": s['rec_text'], "점수": f"{s['score']}점"
            })
        st.dataframe(pd.DataFrame(summary).set_index("순위"), use_container_width=True)

        st.divider()

        # [B] 상세 카드
        for i, s in enumerate(results):
            with st.container(border=True):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(f"#### [#{i+1} {s['name']}]({s['link']})")
                    st.caption(s['ticker'])
                with c2:
                    st.markdown(f"""<div style="background-color:{s['rec_bg']}; color:{s['rec_color']}; padding:5px; border-radius:5px; text-align:center; font-weight:bold; font-size:13px;">{s['rec_text']} ({s['score']})</div>""", unsafe_allow_html=True)
                
                st.write("")
                m1, m2, m3 = st.columns(3)
                with m1: st.markdown(f"""<div style='line-height:1.2'><span style='font-size:18px; font-weight:bold'>{s['price_main']}</span><br><span style='font-size:12px; color:gray'>{s['price_sub']}</span></div>""", unsafe_allow_html=True)
                with m2: 
                    color = "red" if s['change_pct'] > 0 else "blue"
                    st.markdown(f"<span style='color:{color}; font-size:18px; font-weight:bold'>{s['change_pct']:.2f}%</span>", unsafe_allow_html=True)
                with m3:
                    rsi_color = "red" if s['rsi'] >= 75 else ("black" if s['rsi'] >= 30 else "blue")
                    st.markdown(f"<span style='color:{rsi_color}; font-size:18px; font-weight:bold'>{s['rsi']:.0f}</span>", unsafe_allow_html=True)

                # AI 가이드 (추세추종 반영)
                st.markdown(f"""
                <div style='background-color:#f0f2f6; padding:8px; border-radius:8px; margin-top:10px; font-size:14px;'>
                    <b>⚡ AI 매매 가이드 (Trend Riding)</b><br>
                    🎯 목표: <b>♾️ 추세 끝까지</b> &nbsp;|&nbsp; 🛡️ 손절: <b>{s['stop_str']} (20일선)</b>
                </div>""", unsafe_allow_html=True)
                
                df = s['df']
                fig, ax = plt.subplots(figsize=(6, 2.5))
                ax.plot(df.index, df['Close'], color='black', lw=1)
                ax.plot(df.index, s['bb_up'], color='gray', ls='--', alpha=0.5)
                ax.plot(df.index, s['ma20'], color='orange', alpha=0.8)
                ax.set_xticks([]); ax.set_yticks([])
                for sp in ax.spines.values(): sp.set_visible(False)
                ax.grid(False)
                if s['is_breakout']: ax.plot(df.index[-1], df['Close'].iloc[-1], 'ro')
                st.pyplot(fig); plt.close(fig)

# =========================================================
# [탭 2] 백테스팅 (실시간 결과 연동)
# =========================================================
with tab2:
    st.subheader("🧪 검색된 종목 검증하기")
    
    # 실시간 분석 결과가 있는지 확인
    if 'analysis_results' in st.session_state and st.session_state['analysis_results']:
        results = st.session_state['analysis_results']
        
        # Selectbox에 검색된 종목들만 채우기
        options = {f"{s['name']} ({s['ticker']})": s['ticker'] for s in results}
        
        selected_key = st.selectbox("방금 검색된 종목 중 선택:", list(options.keys()))
        
        if st.button("🧪 검증 시작 (1년치 시뮬레이션)", type="primary"):
            target_ticker = options[selected_key]
            
            # 진행바
            my_bar = st.progress(0, text="데이터 분석 중...")
            
            res = run_backtest(target_ticker)
            my_bar.progress(100, text="완료!")
            
            if res is None or res['Count'] == 0:
                st.warning("⚠️ 매매 신호가 없었거나 데이터가 부족합니다.")
            else:
                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                col_ret = "red" if res['Total'] < 0 else "green"
                c1.metric("총 수익률", f"{res['Total']:.1f}%")
                c2.metric("승률", f"{res['Win_Rate']:.0f}%")
                c3.metric("매매 횟수", f"{res['Count']}회")
                
                st.line_chart(res['Equity'])
                
                with st.expander("📝 상세 매매 일지"):
                    st.dataframe(pd.DataFrame(res['Log']), use_container_width=True)
                
                # 코멘트
                if res['Total'] > 30:
                    st.success("🎉 **대박 패턴 발견!** 추세가 아주 강한 종목입니다.")
                elif res['Total'] > 0:
                    st.info("✅ **양호함.** 꾸준히 우상향하는 추세입니다.")
                else:
                    st.error("🛑 **주의.** 휩소(거짓신호)가 많은 종목입니다.")

    else:
        # 분석 결과가 없을 때
        st.info("👈 **[실시간 발굴] 탭에서 먼저 분석을 실행해주세요.**\n\n검색된 Top 10 종목을 여기서 바로 검증할 수 있습니다.")
