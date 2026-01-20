import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr # 종목 리스트 가져오기용
import pandas as pd
import matplotlib.pyplot as plt
import platform
from datetime import datetime

# ---------------------------------------------------------
# 0. 페이지 설정 및 한글 폰트
# ---------------------------------------------------------
st.set_page_config(page_title="무릎 매매 스캐너 Pro", layout="centered")

try:
    import koreanize_matplotlib
except ImportError:
    system_name = platform.system()
    if system_name == 'Windows':
        plt.rc('font', family='Malgun Gothic')
    elif system_name == 'Darwin':
        plt.rc('font', family='AppleGothic')
    else:
        plt.rc('font', family='NanumGothic')
plt.rc('axes', unicode_minus=False)

st.title("🦵 무릎 매매 스캐너 (Auto)")
st.caption("시가총액 상위 종목을 자동으로 수집하여 '무릎(눌림목)'을 찾습니다.")

# ---------------------------------------------------------
# 1. 데이터 수집 함수 (자동화 핵심)
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_stock_list(market_type, limit=30):
    """
    시장별 시가총액 상위 N개 종목 코드를 가져옵니다.
    """
    if market_type == "KOSPI":
        df = fdr.StockListing('KOSPI')
        # 우선주 제외, 상위 N개
        df = df[~df['Code'].str.contains('50$|70$|75$|55$|60$')] # 우선주 등 필터링 대략
        top_list = df.head(limit)
        # yfinance용 티커로 변환 (005930 -> 005930.KS)
        return [(f"{row['Code']}.KS", row['Name']) for _, row in top_list.iterrows()]
    
    elif market_type == "KOSDAQ":
        df = fdr.StockListing('KOSDAQ')
        top_list = df.head(limit)
        return [(f"{row['Code']}.KQ", row['Name']) for _, row in top_list.iterrows()]
    
    elif market_type == "S&P500":
        df = fdr.StockListing('S&P500')
        top_list = df.head(limit)
        return [(row['Symbol'], row['Name']) for _, row in top_list.iterrows()]
    
    elif market_type == "NASDAQ":
        df = fdr.StockListing('NASDAQ')
        top_list = df.head(limit)
        return [(row['Symbol'], row['Name']) for _, row in top_list.iterrows()]
    
    return []

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        df = yf.download("KRW=X", period="1d", progress=False)
        return float(df['Close'].iloc[-1])
    except: return 1450.0

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ---------------------------------------------------------
# 2. 분석 로직
# ---------------------------------------------------------
def analyze_stocks(stock_list):
    results = []
    exchange_rate = get_exchange_rate()
    
    # 진행 상황 표시바
    progress_text = "데이터 수집 및 분석 중입니다. 잠시만 기다려주세요..."
    my_bar = st.progress(0, text=progress_text)
    
    total = len(stock_list)
    tickers = [item[0] for item in stock_list] # 티커만 추출
    names = {item[0]: item[1] for item in stock_list} # 티커:이름 매핑

    # 데이터 한꺼번에 다운로드 (속도 향상)
    try:
        data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', threads=True, progress=False, auto_adjust=True)
    except:
        st.error("데이터 다운로드 중 오류 발생")
        return []

    for i, ticker in enumerate(tickers):
        # 진행바 업데이트
        my_bar.progress((i + 1) / total)
        
        try:
            if len(tickers) == 1: df = data
            else: df = data[ticker] if ticker in data.columns.levels[0] else pd.DataFrame()

            if df.empty or len(df) < 60: continue
            if df['Close'].isna().all(): continue

            close = df['Close']
            curr_price = float(close.iloc[-1])
            
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean()
            
            curr_ma20 = float(ma20.iloc[-1])
            curr_ma60 = float(ma60.iloc[-1])
            prev_ma20 = float(ma20.iloc[-2])
            
            # 이격도
            disparity = ((curr_price - curr_ma20) / curr_ma20) * 100
            
            score = 0
            
            # [로직 1] 정배열 (Trend)
            if curr_ma20 > curr_ma60: 
                score += 30
                if curr_ma20 > prev_ma20: score += 10
            else:
                score -= 20 # 역배열 감점
            
            # [로직 2] 눌림목 위치 (Position)
            if curr_price >= curr_ma20:
                if disparity <= 3.0: score += 40      # Golden Zone
                elif disparity <= 6.0: score += 20    # Good Zone
                else: score += 5                      # Too High
            else:
                score -= 30 # Broken Trend
                
            # [로직 3] RSI
            rsi = calculate_rsi(close).iloc[-1]
            if 30 <= rsi <= 60: score += 20
            
            # 등급 판정
            if score >= 80:
                rec_text = "🦵 강력 무릎"
                rec_bg = "#d4edda"; rec_color = "#155724"
            elif score >= 50:
                rec_text = "🤔 매수 관점"
                rec_bg = "#fff3cd"; rec_color = "#856404"
            else:
                rec_text = "❌ 관망 필요"
                rec_bg = "#f8d7da"; rec_color = "#721c24"

            # 가격 처리
            is_us = not (".KS" in ticker or ".KQ" in ticker)
            if is_us:
                price_str = f"${curr_price:,.2f}"
                krw_price = f"{curr_price * exchange_rate:,.0f}원"
            else:
                price_str = f"{curr_price:,.0f}원"
                krw_price = ""

            results.append({
                'ticker': ticker,
                'name': names[ticker],
                'score': score,
                'rec_text': rec_text, 'rec_bg': rec_bg, 'rec_color': rec_color,
                'price': price_str, 'krw': krw_price,
                'disparity': disparity,
                'df': df
            })

        except Exception: continue
        
    my_bar.empty() # 진행바 제거
    
    # 점수 높은 순 정렬
    results.sort(key=lambda x: x['score'], reverse=True)
    return results

# ---------------------------------------------------------
# 3. 백테스팅 함수
# ---------------------------------------------------------
def run_backtest(ticker, period="1y"):
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty or len(df) < 60: return None
        
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        balance = 1000000; shares = 0; in_position = False
        trade_log = []; equity_curve = []
        
        for i in range(60, len(df)):
            date = df.index[i]
            row = df.iloc[i]
            curr_equity = balance + (shares * row['Close'])
            equity_curve.append({'Date': date, 'Equity': curr_equity})
            
            # 매도 (20일선 이탈)
            if in_position and row['Close'] < row['MA20']:
                balance += shares * row['Close']
                yield_rate = ((row['Close'] - buy_price)/buy_price)*100
                trade_log.append({'구분': '매도', '수익률': f"{yield_rate:.2f}%", '날짜': date})
                shares = 0; in_position = False
            
            # 매수 (정배열 + 지지 + 이격도 3% 이내)
            elif not in_position and row['MA20'] > row['MA60'] and row['Close'] >= row['MA20'] and row['Close'] <= row['MA20']*1.03:
                buy_price = row['Close']
                shares = balance / buy_price
                balance = 0; in_position = True
                trade_log.append({'구분': '매수', '수익률': '-', '날짜': date})

        final_equity = shares * df['Close'].iloc[-1] if in_position else balance
        total_ret = ((final_equity - 1000000)/1000000)*100
        
        wins = [1 for t in trade_log if t['구분']=='매도' and '-' not in t['수익률'] and float(t['수익률'][:-1]) > 0]
        total_trades = len([t for t in trade_log if t['구분']=='매도'])
        win_rate = (sum(wins)/total_trades*100) if total_trades > 0 else 0
        
        return {'Total': total_ret, 'Win_Rate': win_rate, 'Count': total_trades, 'Equity': pd.DataFrame(equity_curve).set_index('Date'), 'Log': trade_log}
    except: return None

# ---------------------------------------------------------
# 4. 화면 구성 (UI)
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📊 자동 종목 스캔", "🧪 수익률 검증"])

with tab1:
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        market = st.selectbox("시장 선택", ["S&P500", "NASDAQ", "KOSPI", "KOSDAQ"])
    with col_opt2:
        top_n = st.selectbox("분석할 종목 수", [30, 50, 100], index=0)

    if st.button("🔍 상위 종목 자동 분석 시작", type="primary"):
        stock_list = get_stock_list(market, top_n)
        st.session_state['auto_results'] = analyze_stocks(stock_list)

    if 'auto_results' in st.session_state and st.session_state['auto_results']:
        results = st.session_state['auto_results']
        st.success(f"총 {len(results)}개 종목 분석 완료!")
        
        for item in results:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(f"### {item['name']}")
                    st.caption(item['ticker'])
                with c2:
                    st.markdown(f"#### {item['price']}")
                    if item['krw']: st.caption(f"({item['krw']})")
                with c3:
                    st.markdown(f"""<div style="background-color:{item['rec_bg']}; color:{item['rec_color']}; padding:8px; border-radius:5px; text-align:center; font-weight:bold;">{item['rec_text']}</div>""", unsafe_allow_html=True)
                
                # 미니 차트
                df = item['df'][-60:]
                fig, ax = plt.subplots(figsize=(8, 1.5))
                ax.plot(df.index, df['Close'], color='black')
                ax.plot(df.index, df['Close'].rolling(20).mean()[-60:], color='green', lw=2, label='20일선')
                ax.legend(fontsize='small')
                ax.set_xticks([]); ax.set_yticks([])
                for sp in ax.spines.values(): sp.set_visible(False)
                st.pyplot(fig); plt.close(fig)

with tab2:
    if 'auto_results' in st.session_state and st.session_state['auto_results']:
        opts = {f"{r['name']} ({r['ticker']})": r['ticker'] for r in st.session_state['auto_results']}
        sel = st.selectbox("종목 선택", list(opts.keys()))
        
        if st.button("검증 시작"):
            res = run_backtest(opts[sel])
            if res:
                c1, c2, c3 = st.columns(3)
                c1.metric("수익률", f"{res['Total']:.1f}%")
                c2.metric("승률", f"{res['Win_Rate']:.1f}%")
                c3.metric("매매횟수", f"{res['Count']}회")
                st.line_chart(res['Equity'])
                st.dataframe(res['Log'])
    else:
        st.info("먼저 [자동 종목 스캔] 탭에서 분석을 실행해주세요.")
