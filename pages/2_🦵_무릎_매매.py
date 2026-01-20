import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
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

st.title("🦵 무릎 매매 스캐너 ")
st.caption("시가총액 상위 종목을 자동 분석하여 매매 타점을 제시합니다.")

# ---------------------------------------------------------
# 1. 데이터 수집 함수
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_stock_list(market_type, limit=30):
    if market_type == "KOSPI":
        df = fdr.StockListing('KOSPI')
        df = df[~df['Code'].str.contains('50$|70$|75$|55$|60$')]
        top_list = df.head(limit)
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
    
    progress_text = "데이터 수집 및 정밀 분석 중... (매수가/손절가 계산)"
    my_bar = st.progress(0, text=progress_text)
    
    total = len(stock_list)
    tickers = [item[0] for item in stock_list]
    names = {item[0]: item[1] for item in stock_list}

    try:
        data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', threads=True, progress=False, auto_adjust=True)
    except:
        st.error("데이터 다운로드 중 오류 발생")
        return []

    for i, ticker in enumerate(tickers):
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
            
            disparity = ((curr_price - curr_ma20) / curr_ma20) * 100
            
            score = 0
            
            # [점수 로직]
            if curr_ma20 > curr_ma60: 
                score += 30
                if curr_ma20 > prev_ma20: score += 10
            else: score -= 20
            
            if curr_price >= curr_ma20:
                if disparity <= 3.0: score += 40
                elif disparity <= 6.0: score += 20
                else: score += 5
            else: score -= 30
                
            rsi = calculate_rsi(close).iloc[-1]
            if 30 <= rsi <= 60: score += 20
            
            # [등급 및 색상]
            if score >= 80:
                rec_text = "🦵 강력 무릎 (적극매수)"
                rec_bg = "#d4edda"; rec_color = "#155724"
            elif score >= 50:
                rec_text = "🤔 매수 관점"
                rec_bg = "#fff3cd"; rec_color = "#856404"
            else:
                rec_text = "❌ 관망 필요"
                rec_bg = "#f8d7da"; rec_color = "#721c24"

            # [가격 가이드 문자열 생성]
            is_us = not (".KS" in ticker or ".KQ" in ticker)
            
            if is_us:
                p_curr = f"${curr_price:,.2f}"
                p_stop = f"${curr_ma20:,.2f}"
                p_krw = f"{curr_price * exchange_rate:,.0f}원"
            else:
                p_curr = f"{curr_price:,.0f}원"
                p_stop = f"{curr_ma20:,.0f}원"
                p_krw = ""

            results.append({
                'ticker': ticker, 'name': names[ticker], 'score': score,
                'rec_text': rec_text, 'rec_bg': rec_bg, 'rec_color': rec_color,
                'price': p_curr, 'krw': p_krw, 'stop_price': p_stop,
                'df': df, 'ma20': curr_ma20
            })

        except Exception: continue
        
    my_bar.empty()
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
        
        balance = 1000000; shares = 0; in_position = False; buy_price = 0
        trade_log = []; equity_curve = []
        
        for i in range(60, len(df)):
            date = df.index[i]
            row = df.iloc[i]
            curr_equity = balance + (shares * row['Close'])
            equity_curve.append({'Date': date, 'Equity': curr_equity})
            
            if in_position and row['Close'] < row['MA20']:
                balance += shares * row['Close']
                yield_rate = ((row['Close'] - buy_price)/buy_price)*100
                trade_log.append({'구분': '매도', '수익률': f"{yield_rate:.2f}%", '날짜': date})
                shares = 0; in_position = False
            
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
# 4. 화면 구성 (UI) - 안전장치 추가됨
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📊 자동 종목 스캔", "🧪 수익률 검증"])

with tab1:
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        market = st.selectbox("시장 선택", ["S&P500", "NASDAQ", "KOSPI", "KOSDAQ"])
    with col_opt2:
        top_n = st.selectbox("분석할 종목 수", [30, 50, 100], index=0)

    # 데이터가 꼬였을 때를 대비해 세션 초기화 버튼 추가
    if st.button("🔍 종목 분석 및 타점 계산 (새로고침)", type="primary"):
        # 기존 데이터 삭제 (에러 방지 핵심)
        if 'auto_results' in st.session_state:
            del st.session_state['auto_results']
            
        stock_list = get_stock_list(market, top_n)
        st.session_state['auto_results'] = analyze_stocks(stock_list)

    if 'auto_results' in st.session_state and st.session_state['auto_results']:
        results = st.session_state['auto_results']
        st.success(f"총 {len(results)}개 종목 분석 완료!")
        
        for item in results:
            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.markdown(f"### {item['name']}")
                    st.caption(item['ticker'])
                with c2:
                    st.markdown(f"""<div style="background-color:{item['rec_bg']}; color:{item['rec_color']}; padding:8px; border-radius:5px; text-align:center; font-weight:bold;">{item['rec_text']} ({item['score']}점)</div>""", unsafe_allow_html=True)
                
                st.markdown("---")
                g1, g2, g3 = st.columns(3)
                
                # [수정됨] .get()을 사용하여 데이터가 없어도 에러가 나지 않게 처리
                with g1:
                    st.metric("현재가 (매수)", item.get('price', '-'))
                    if item.get('krw'): st.caption(f"({item['krw']})")
                with g2:
                    st.metric("손절가 (20일선)", item.get('stop_price', '계산중...'))
                    st.caption("이 가격 깨지면 매도")
                with g3:
                    st.metric("목표 전략", "추세 추종 🚀")
                    st.caption("20일선 위면 계속 보유")
                
                # 차트 섹션
                if 'df' in item and not item['df'].empty:
                    df = item['df'][-60:]
                    fig, ax = plt.subplots(figsize=(8, 1.5))
                    ax.plot(df.index, df['Close'], color='black', label='주가')
                    # ma20이 없으면 계산
                    ma20 = df['Close'].rolling(20).mean()
                    ax.plot(df.index, ma20, color='green', lw=2, label='생명선(손절선)')
                    ax.fill_between(df.index, df['Close'], ma20, color='green', alpha=0.1)
                    ax.legend(fontsize='small', loc='upper left')
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
