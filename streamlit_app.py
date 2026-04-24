import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.linear_model import LinearRegression

st.set_page_config(page_title="币安永续合约上升通道扫描", page_icon="📈")

st.title("📈 币安永续合约上升通道扫描")
st.markdown("实时扫描574个币安U本位永续合约，找出上升通道模型")

@st.cache_data(ttl=300)
def get_perpetual_symbols():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    response = requests.get(url, timeout=10)
    data = response.json()
    symbols = []
    for s in data['symbols']:
        if s['contractType'] == 'PERPETUAL' and s['status'] == 'TRADING':
            symbols.append({
                'symbol': s['symbol'],
                'baseAsset': s['baseAsset'],
                'onboardDate': s.get('onboardDate', '20200101')
            })
    return symbols

def get_klines(symbol, limit=100):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=5m&limit={limit}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and len(data) > 10:
            closes = [float(c[4]) for c in data]
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            return closes, highs, lows
    except:
        pass
    return None, None, None

def check_uptrend(closes, highs, lows):
    if len(closes) < 20:
        return None
    try:
        X = np.arange(len(closes)).reshape(-1, 1)
        reg = LinearRegression().fit(X, closes)
        slope = reg.coef_[0]
        r_squared = reg.score(X, closes)
        channel_angle = (slope / np.mean(closes)) * 100 if np.mean(closes) > 0 else 0
        if channel_angle > 0.001 and r_squared > 0.5:
            current = closes[-1]
            reg_h = LinearRegression().fit(X, np.array(highs))
            reg_l = LinearRegression().fit(X, np.array(lows))
            upper = reg_h.predict(X)[-1]
            lower = reg_l.predict(X)[-1]
            mid = (upper + lower) / 2
            if lower < current < upper:
                if current < mid * 0.95:
                    position = "🟢下轨"
                elif current > mid * 1.05:
                    position = "🔴上轨"
                else:
                    position = "🟡中部"
                return {
                    'slope': slope,
                    'r_squared': r_squared,
                    'channel_angle': channel_angle,
                    'position': position,
                    'current': current
                }
    except:
        pass
    return None

def get_price(symbol):
    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
    try:
        r = requests.get(url, timeout=3)
        return float(r.json()['price'])
    except:
        return None

if 'results' not in st.session_state:
    st.session_state.results = None
if 'last_update' not in st.session_state:
    st.session_state.last_update = None

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🔄 立即扫描", type="primary", use_container_width=True):
        with st.spinner("正在扫描..."):
            symbols = get_perpetual_symbols()
            results = []
            progress_bar = st.progress(0)
            for i, s in enumerate(symbols):
                result = check_uptrend(*get_klines(s['symbol']))
                if result:
                    result['symbol'] = s['symbol'].replace('USDT', '')
                    result['onboardDate'] = s['onboardDate']
                    result['price'] = get_price(s['symbol'])
                    results.append(result)
                progress_bar.progress((i + 1) / len(symbols))
            
            results.sort(key=lambda x: x['onboardDate'], reverse=True)
            st.session_state.results = results
            st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

with col2:
    st.metric("发现通道", len(st.session_state.results) if st.session_state.results else 0)

with col3:
    st.text(f"更新时间\n{st.session_state.last_update or '-'}")

if st.session_state.results:
    df = pd.DataFrame(st.session_state.results)
    df = df.sort_values('onboardDate', ascending=False)
    
    st.subheader("🏆 上升通道列表（按上架时间排序）")
    
    for _, row in df.iterrows():
        date_str = row['onboardDate']
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            days_ago = (datetime.now() - date_obj).days
            date_display = f"{date_obj.strftime('%m-%d')} ({days_ago}天)"
        except:
            date_display = date_str
        
        with st.container():
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"### {row['symbol']}")
                st.write(f"📅 {date_display} | 💰 ${row['price']:.4f} | 📈 {row['channel_angle']:.4f}% | R² {row['r_squared']:.2f}")
            with col_b:
                st.markdown(f"## {row['position']}")
            st.markdown("---")
else:
    st.info("👆 点击上方「立即扫描」开始实时扫描币安永续合约")

st.caption("📊 数据来源：币安API | 每5分钟K线 | 上升通道判定：线性回归 R²>0.5")
