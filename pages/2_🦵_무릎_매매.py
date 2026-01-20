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
st.set_page_config(page_title="무릎 매매 스캐너", layout="centered")

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

# [타이틀 고정]
st.title("🦵 무릎 매매 스캐너 ")
st.caption("거래량 분석과 익절/손절 로직을 강화하여 승률을 극대화한 버전입니다.")

# ---------------------------------------------------------
# 1. 유틸리티 함수
# ---------------------------------------------------------
def get_stock_link(ticker):
    if ".KS" in ticker or ".KQ" in ticker:
        code = ticker.split('.')[0]
        return f"https://finance.naver.com/item/main.naver?code={code}"
    else:
        return f"https://finance.yahoo.com/quote/{ticker}"

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
# 2. 분석 로직 (강화된 필터 적용)
# ---------------------------------------------------------
def analyze_stocks(stock_list):
    results = []
    exchange_rate = get_exchange_rate()
    
    progress_text = "데이터 수집 및 정밀 분석 중... (거래량 & 추세 분석)"
    my_bar = st.progress(0, text=progress_text)
    
    total = len(stock_list)
    tickers = [item[0] for item in stock_list]
    names = {item[0]: item[1] for item in stock_list}

    try:
        data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', threads=True, progress=False, auto_adjust=True)
    except:
        st.error("데이터 다운로드 실패.")
        return []

    for i, ticker in enumerate(tickers):
        my_bar.progress((i + 1) / total)
        try:
            if len(tickers) == 1: df = data
            else: df = data[ticker] if ticker in data.columns.levels[0] else pd.DataFrame()

            if isinstance(df, pd.DataFrame):
                if 'Close' in df.columns: close = df['Close']; volume = df['Volume']
                else: continue
            else: close = df; volume = df # Series인 경우
                
            if close.isna().all(): continue
            if len(close) < 60: continue

            curr_price = float(close.iloc[-1])
            curr_vol = float(volume.iloc[-1])
            
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean()
            vol_ma20 = volume.rolling(20).mean() # 거래량 이평선
            
            curr_ma20 = float(ma20.iloc[-1])
            curr_ma60 = float(ma60.iloc[-1])
            prev_ma20 = float(ma20.iloc[-2])
            curr_vol_ma20 = float(vol_ma20.iloc[-1])
            
            disparity = ((curr_price - curr_ma20) / curr_ma20) * 100
            
            score = 0
            reasons = [] 
            
            # [1] 추세 점수 (Trend)
            if curr_ma20 > curr_ma60: 
                score += 30
                reasons.append("✅ 정배열 (상승 추세) [+30점]")
                if curr_ma20 > prev_ma20: 
                    score += 10
                    reasons.append("📈 20일선 상승 각도 좋음 [+10점]")
            else:
                score -= 30
                reasons.append("⚠️ 역배열 (하락 추세) [-30점]")
            
            # [2] 위치 점수 (Position) - 무릎인가?
            if curr_price >= curr_ma20:
                if disparity <= 3.0: 
                    score += 40
                    reasons.append("🦵 완벽한 무릎 (이격도 3% 이내) [+40점]")
                elif disparity <= 6.0: 
                    score += 20
                    reasons.append("👌 매수 유효 (이격도 6% 이내) [+20점]")
                else: 
                    reasons.append("😅 위치 높음 (추격매수 주의) [0점]")
            else:
                # 20일선 살짝 깬 건 괜찮음 (개미털기 가능성) -1%까진 봐줌
                if disparity >= -1.0:
                    score += 20
                    reasons.append("🔍 20일선 살짝 하회 (지지 테스트 중) [+20점]")
                else:
                    score -= 50
                    reasons.append("🚫 20일선 붕괴 위험 [-50점]")

            # [3] 수급 점수 (Volume) - 거래량이 실렸는가?
            if curr_vol >= curr_vol_ma20 * 0.8: # 평소 거래량의 80% 이상은 되어야 함
                score += 20
                reasons.append("📊 거래량 양호 (수급 받쳐줌) [+20점]")
            else:
                reasons.append("💤 거래량 부족 (관심 부족) [0점]")

            # 등급 판정
            if score >= 80:
                rec_text = "💎 강력 추천"; rec_bg = "#d4edda"; rec_color = "#155724"
            elif score >= 60:
                rec_text = "🤔 매수 고려"; rec_bg = "#fff3cd"; rec_color = "#856404"
            else:
                rec_text = "❌ 관망 필요"; rec_bg = "#f8d7da"; rec_color = "#721c24"

            link = get_stock_link(ticker)
            is_us = not (".KS" in ticker or ".KQ" in ticker)
            
            # 손절가는 타이트하게 잡음 (진입가 -3% 또는 20일선 중 높은 가격)
            stop_loss_price = max(curr_price * 0.97, curr_ma20)
            
            if is_us:
                p_curr = f"${curr_price:,.2f}"
                p_stop = f"${stop_loss_price:,.2f}"
                p_krw = f"{curr_price * exchange_rate:,.0f}원"
            else:
                p_curr = f"{curr_price:,.0f}원"
                p_stop = f"{stop_loss_price:,.0f}원"
                p_krw = ""

            results.append({
                'ticker': ticker, 'name': names[ticker], 'link': link,
                'score': score, 'reasons': reasons,
                'rec_text': rec_text, 'rec_bg': rec_bg, 'rec_color': rec_color,
                'price': p_curr, 'krw': p_krw, 'stop_price': p_stop,
                'df': df
            })

        except Exception: continue
        
    my_bar.empty()
    results.sort(key=lambda x: x['score'], reverse=True)
    return results

# ---------------------------------------------------------
# 3. 백테스팅 함수 (스마트 매매: 익절 + 칼손절)
# ---------------------------------------------------------
def run_backtest(ticker, period="1y"):
    """
    [개선된 로직]
    1. 매수: 정배열 + 눌림목
    2. 매도 (익절): 수익률 +7% 도달 시 전량 매도 (확실한 수익 챙기기)
    3. 매도 (손절): 진입가 대비 -3% 하락 시 칼손절 (손실 최소화)
    4. 매도 (추세): 20일선 이탈 시 매도
    """
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            try: df.columns = df.columns.droplevel(1) 
            except: pass

        if df.empty or len(df) < 60:
            st.error("데이터 부족")
            return None
        
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        balance = 1000000; shares = 0; in_position = False; buy_price = 0
        trade_log = []; equity_curve = []
        
        # 목표 수익률과 손절율 설정
        TARGET_PROFIT = 0.07  # +7% 익절
        STOP_LOSS = 0.03      # -3% 손절
        
        for i in range(60, len(df)):
            date = df.index[i]
            row = df.iloc[i]
            close_price = float(row['Close'])
            ma20 = float(row['MA20'])
            ma60 = float(row['MA60'])
            
            # 자산 가치 기록
            if in_position: curr_equity = shares * close_price
            else: curr_equity = balance
            equity_curve.append({'Date': date, 'Equity': curr_equity})
            
            # --- [매도 로직] ---
            if in_position:
                # 1. 익절 조건 (+7% 달성)
                if close_price >= buy_price * (1 + TARGET_PROFIT):
                    balance = shares * close_price
                    yield_rate = ((close_price - buy_price)/buy_price)*100
                    trade_log.append({'구분': '💰익절', '수익률': f"+{yield_rate:.1f}%", '날짜': date})
                    shares = 0; in_position = False
                
                # 2. 칼손절 조건 (-3% 하락)
                elif close_price <= buy_price * (1 - STOP_LOSS):
                    balance = shares * close_price
                    yield_rate = ((close_price - buy_price)/buy_price)*100
                    trade_log.append({'구분': '💧손절', '수익률': f"{yield_rate:.1f}%", '날짜': date})
                    shares = 0; in_position = False

                # 3. 추세 이탈 (20일선 붕괴)
                elif close_price < ma20:
                    balance = shares * close_price
                    yield_rate = ((close_price - buy_price)/buy_price)*100
                    trade_log.append({'구분': '📉이탈', '수익률': f"{yield_rate:.1f}%", '날짜': date})
                    shares = 0; in_position = False
            
            # --- [매수 로직] ---
            # 조건: 정배열 + 눌림목(3%이내) + (중요) 어제보다 오늘 주가가 오름(반등시그널)
            elif not in_position:
                prev_close = float(df['Close'].iloc[i-1])
                
                cond_trend = ma20 > ma60
                cond_knee = close_price >= ma20 and close_price <= ma20 * 1.05
                cond_up = close_price > prev_close # 양봉 또는 상승 전환
                
                if cond_trend and cond_knee and cond_up:
                    buy_price = close_price
                    shares = balance / buy_price
                    balance = 0; in_position = True
                    trade_log.append({'구분': '🚀매수', '수익률': '-', '날짜': date})

        final_equity = shares * df['Close'].iloc[-1] if in_position else balance
        total_ret = ((final_equity - 1000000)/1000000)*100
        
        wins = [1 for t in trade_log if '익절' in t['구분'] or ('이탈' in t['구분'] and '-' not in t['수익률'])]
        total_trades = len([t for t in trade_log if t['구분']!='매수'])
        win_rate = (sum(wins)/total_trades*100) if total_trades > 0 else 0
        
        return {
            'Total': total_ret, 'Win_Rate': win_rate, 'Count': total_trades, 
            'Equity': pd.DataFrame(equity_curve).set_index('Date'), 'Log': trade_log
        }

    except Exception as e:
        st.error(f"백테스팅 오류: {str(e)}")
        return None

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

    if st.button("🔍 종목 분석 시작 (새로고침)", type="primary"):
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
                    link = item.get('link', '#')
                    st.markdown(f"### [{item['name']}]({link})")
                    st.caption(item['ticker'])
                with c2:
                    st.markdown(f"""<div style="background-color:{item['rec_bg']}; color:{item['rec_color']}; padding:8px; border-radius:5px; text-align:center; font-weight:bold;">{item['rec_text']} ({item['score']}점)</div>""", unsafe_allow_html=True)
                
                with st.expander(f"💯 점수 상세 보기 ({len(item.get('reasons', []))}개 항목)"):
                    if item.get('reasons'):
                        for r in item['reasons']: st.write(r)
                    else: st.write("특이 사항 없음")

                st.markdown("---")
                g1, g2, g3 = st.columns(3)
                with g1:
                    st.metric("현재가 (매수)", item.get('price', '-'))
                    if item.get('krw'): st.caption(f"({item['krw']})")
                with g2:
                    st.metric("칼손절가 (-3%)", item.get('stop_price', '-'))
                    st.caption("20일선 또는 -3% 중 높은 가격")
                with g3:
                    st.metric("목표 수익", "+7% 💰")
                    st.caption("달성 시 자동 익절 추천")
                
                if 'df' in item and not item['df'].empty:
                    df = item['df'][-60:]
                    fig, ax = plt.subplots(figsize=(8, 1.5))
                    ax.plot(df.index, df['Close'], color='black', label='주가')
                    ma20 = df['Close'].rolling(20).mean()
                    ax.plot(df.index, ma20, color='green', lw=2, label='생명선')
                    ax.fill_between(df.index, df['Close'], ma20, color='green', alpha=0.1)
                    ax.legend(fontsize='small', loc='upper left')
                    ax.set_xticks([]); ax.set_yticks([])
                    for sp in ax.spines.values(): sp.set_visible(False)
                    st.pyplot(fig); plt.close(fig)

with tab2:
    if 'auto_results' in st.session_state and st.session_state['auto_results']:
        opts = {f"{r['name']} ({r['ticker']})": r['ticker'] for r in st.session_state['auto_results']}
        sel = st.selectbox("종목 선택", list(opts.keys()))
        
        if st.button("🧪 스마트 검증 시작"):
            with st.spinner("익절 +7% / 손절 -3% 전략으로 시뮬레이션 중..."):
                res = run_backtest(opts[sel])
                
            if res:
                c1, c2, c3 = st.columns(3)
                color = "green" if res['Total'] > 0 else "red"
                c1.markdown(f"**수익률**")
                c1.markdown(f"<h2 style='color:{color}'>{res['Total']:.1f}%</h2>", unsafe_allow_html=True)
                c2.metric("승률", f"{res['Win_Rate']:.1f}%")
                c3.metric("매매횟수", f"{res['Count']}회")
                st.line_chart(res['Equity'])
                st.dataframe(res['Log'])
    else:
        st.info("먼저 [자동 종목 스캔] 탭에서 분석을 실행해주세요.")
