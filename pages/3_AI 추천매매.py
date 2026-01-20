import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 1. 설정 및 데이터 수집 (Configuration & Data Fetching)
# ---------------------------------------------------------

# 추천 종목 리스트 (티커)
tickers = [
    'NVDA', 'MSFT', 'AMZN', 'NOW',  # Tech & AI
    'WMT', 'ISRG', 'LMT',           # Defensive & Healthcare
    'NEE', 'SHOP', 'PYPL'           # Growth & Turnaround
]

# 분석 기간 설정 (최근 1년 데이터)
end_date = datetime.now()
start_date = end_date - timedelta(days=365)

print(f"[{datetime.now().strftime('%Y-%m-%d')}] 미국 주식 추천 종목 10선 분석을 시작합니다...")

# 데이터 다운로드 함수
def get_stock_data(tickers, start, end):
    data = yf.download(tickers, start=start, end=end)['Close']
    return data

try:
    stock_data = get_stock_data(tickers, start_date, end_date)
    print("데이터 다운로드 완료.\n")
except Exception as e:
    print(f"데이터 다운로드 중 오류 발생: {e}")
    stock_data = pd.DataFrame()

# ---------------------------------------------------------
# 2. 분석 및 시뮬레이션 엔진 (Analysis & Simulation Engine)
# ---------------------------------------------------------

def analyze_and_plot(ticker, data):
    # 해당 종목 데이터 추출
    df = data[ticker].to_frame()
    df.columns = ['Close']
    
    # --- 기술적 지표 계산 ---
    # 이동평균선 (SMA)
    df['SMA_20'] = df['Close'].rolling(window=20).mean() # 단기 추세
    df['SMA_60'] = df['Close'].rolling(window=60).mean() # 중기 추세
    
    # 볼린저 밴드 (변동성 지표)
    df['std'] = df['Close'].rolling(window=20).std()
    df['Upper_Band'] = df['SMA_20'] + (df['std'] * 2)
    df['Lower_Band'] = df['SMA_20'] - (df['std'] * 2)

    # 일일 수익률 및 변동성 (리스크 측정용)
    daily_returns = df['Close'].pct_change().dropna()
    avg_daily_return = daily_returns.mean()
    daily_volatility = daily_returns.std()

    # --- 몬테카를로 시뮬레이션 (미래 예측) ---
    # 향후 30일(거래일 기준) 예측
    days_to_predict = 30
    simulation_count = 100 # 100개의 시나리오 생성
    
    last_price = df['Close'].iloc[-1]
    simulation_df = pd.DataFrame()

    for x in range(simulation_count):
        # 과거의 변동성을 기반으로 랜덤한 미래 가격 생성
        price_series = [last_price]
        for y in range(days_to_predict):
            # 랜덤 충격(Shock) 생성 (정규분포)
            shock = np.random.normal(avg_daily_return, daily_volatility)
            price = price_series[-1] * (1 + shock)
            price_series.append(price)
        
        simulation_df[x] = price_series

    # 예측 평균값 (Expected Path)
    simulation_df['Mean_Path'] = simulation_df.mean(axis=1)

    # ---------------------------------------------------------
    # 3. 시각화 (Visualization)
    # ---------------------------------------------------------
    plt.figure(figsize=(14, 6))
    
    # (1) 과거 데이터 및 기술적 지표
    plt.subplot(1, 2, 1)
    plt.plot(df.index, df['Close'], label='Close Price', color='black', alpha=0.6)
    plt.plot(df.index, df['SMA_20'], label='SMA 20 (Short)', color='orange', linestyle='--')
    plt.plot(df.index, df['SMA_60'], label='SMA 60 (Mid)', color='blue', linestyle='--')
    plt.fill_between(df.index, df['Upper_Band'], df['Lower_Band'], color='gray', alpha=0.1, label='Bollinger Band')
    plt.title(f"[{ticker}] Technical Analysis (1 Year)")
    plt.legend(loc='upper left')
    plt.grid(True, alpha=0.3)

    # (2) 미래 예측 시뮬레이션
    plt.subplot(1, 2, 2)
    
    # 시뮬레이션 날짜 생성
    future_dates = [df.index[-1] + timedelta(days=x) for x in range(days_to_predict + 1)]
    
    # 모든 시나리오 흐릿하게 그리기 (가능한 범위)
    for x in range(simulation_count):
        plt.plot(future_dates, simulation_df[x], color='green', alpha=0.05)
        
    # 평균 예상 경로 진하게 그리기
    plt.plot(future_dates, simulation_df['Mean_Path'], color='red', linewidth=2, label='Expected Path (Avg)')
    
    # 시작점 표시
    plt.axhline(y=last_price, color='black', linestyle=':', label=f'Current: ${last_price:.2f}')
    
    plt.title(f"[{ticker}] Monte Carlo Simulation (Next 30 Days)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # 텍스트 분석 결과 출력
    expected_price = simulation_df['Mean_Path'].iloc[-1]
    roi = ((expected_price - last_price) / last_price) * 100
    
    print(f"📊 [{ticker}] 분석 요약")
    print(f" - 현재 주가: ${last_price:.2f}")
    print(f" - 변동성(Risk): {daily_volatility*100:.2f}% (일일 기준)")
    print(f" - 30일 후 예상 평균 주가: ${expected_price:.2f} (예상 수익률: {roi:+.2f}%)")
    print(f" - 20일 이평선 위치: ${df['SMA_20'].iloc[-1]:.2f} " + 
          ("🟢 상승추세" if last_price > df['SMA_20'].iloc[-1] else "🔴 조정구간"))
    print("-" * 60)

# ---------------------------------------------------------
# 4. 실행 (Execution)
# ---------------------------------------------------------
# 예시로 3개 종목만 먼저 실행해서 보여줍니다. (전체 실행 시 loop 사용)
# 사용자는 아래 리스트를 tickers 전체로 변경하면 됩니다.
selected_preview = ['NVDA', 'WMT', 'NEE'] 

for ticker in selected_preview:
    analyze_and_plot(ticker, stock_data)
