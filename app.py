import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime, timedelta

# ==========================================
# 1. 頁面設定 (鉅亨風格)
# ==========================================
st.set_page_config(page_title="ProQuant X 智能操盤", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #333; }
    .metric-value { font-size: 32px; font-weight: bold; font-family: Arial; }
    .up { color: #eb3f38; }
    .down { color: #2daa59; }
    .log-area { 
        background-color: #000; color: #0f0; 
        font-family: 'Courier New'; padding: 10px; border-radius: 5px; 
        height: 150px; overflow-y: scroll;
    }
    /* 隱藏預設選單 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 模擬數據生成引擎 (取代易卡死的 twstock)
# ==========================================
def generate_mock_data():
    # 產生 100 天的模擬 K 線
    dates = pd.date_range(end=datetime.now(), periods=100)
    base_price = 1000
    
    # 隨機漫步產生價格
    changes = np.random.normal(0, 10, 100)
    prices = base_price + np.cumsum(changes)
    
    df = pd.DataFrame(index=dates)
    df['Date'] = dates
    df['close'] = prices
    df['open'] = df['close'].shift(1) + np.random.normal(0, 5, 100)
    df['high'] = df[['open', 'close']].max(axis=1) + np.random.rand(100) * 10
    df['low'] = df[['open', 'close']].min(axis=1) - np.random.rand(100) * 10
    df['vol'] = np.random.randint(5000, 50000, 100)
    
    # 填補第一筆 NaN
    df.fillna(method='bfill', inplace=True)
    return df

# ==========================================
# 3. 技術指標計算 (Real Logic)
# ==========================================
def calculate_indicators(df):
    # MA
    df['MA5'] = df['close'].rolling(5).mean()
    df['MA20'] = df['close'].rolling(20).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # KD
    low_min = df['low'].rolling(9).min()
    high_max = df['high'].rolling(9).max()
    df['RSV'] = (df['close'] - low_min) / (high_max - low_min) * 100
    df['K'] = df['RSV'].ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()
    
    # MACD
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']
    
    return df

# 初始化 Session
if 'data' not in st.session_state:
    raw_df = generate_mock_data()
    st.session_state.data = calculate_indicators(raw_df)
if 'balance' not in st.session_state:
    st.session_state.balance = 1000000
if 'holdings' not in st.session_state:
    st.session_state.holdings = 0
if 'logs' not in st.session_state:
    st.session_state.logs = []

# ==========================================
# 4. 介面與邏輯
# ==========================================

# --- Sidebar ---
with st.sidebar:
    st.title("🤖 智動操盤 Pro")
    stock_id = st.text_input("股票代號", "2330 台積電")
    
    st.divider()
    st.subheader("策略中心")
    strategy = st.selectbox("選擇策略", ["KD 黃金交叉", "RSI 超賣反彈", "MACD 趨勢突破"])
    auto_active = st.toggle("🔴 啟動自動下單", value=True)
    
    st.divider()
    st.subheader("圖表設定")
    tech_view = st.radio("副圖指標", ["成交量", "RSI", "KD", "MACD"])

# --- Main Content ---

# 1. 模擬即時跳動 (每次刷新增加一點波動)
last_row = st.session_state.data.iloc[-1].copy()
noise = np.random.normal(0, 2)
new_price = last_row['close'] + noise
new_time = last_row['Date'] + timedelta(minutes=1)

# 更新數據 (產生跳動感)
st.session_state.data.at[st.session_state.data.index[-1], 'close'] = new_price
st.session_state.data.at[st.session_state.data.index[-1], 'high'] = max(last_row['high'], new_price)
st.session_state.data.at[st.session_state.data.index[-1], 'low'] = min(last_row['low'], new_price)
# 重新計算指標 (只算最後幾筆以節省效能)
st.session_state.data = calculate_indicators(st.session_state.data)

df = st.session_state.data
current_p = df['close'].iloc[-1]
last_p = df['close'].iloc[-2]
diff = current_p - last_p
color = "up" if diff > 0 else "down"

# 2. 頂部看板
c1, c2, c3 = st.columns([3, 2, 4])
with c1:
    st.markdown(f"## {stock_id}")
with c2:
    st.markdown(f"<div class='metric-value {color}'>{current_p:.2f}</div>", unsafe_allow_html=True)
    st.markdown(f"<span class='{color}'>{diff:+.2f} ({diff/last_p*100:+.2f}%)</span>", unsafe_allow_html=True)
with c3:
    st.info(f"💰 資金: ${st.session_state.balance:,.0f} | 🎒 庫存: {st.session_state.holdings} 張")

st.divider()

# 3. 繪圖
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_width=[0.3, 0.7], vertical_spacing=0.05)

# K線
fig.add_trace(go.Candlestick(x=df['Date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='K線'), row=1, col=1)
fig.add_trace(go.Scatter(x=df['Date'], y=df['MA5'], line=dict(color='orange'), name='MA5'), row=1, col=1)
fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], line=dict(color='blue'), name='MA20'), row=1, col=1)

# 副圖
if tech_view == "成交量":
    fig.add_trace(go.Bar(x=df['Date'], y=df['vol'], marker_color='#999'), row=2, col=1)
elif tech_view == "RSI":
    fig.add_trace(go.Scatter(x=df['Date'], y=df['RSI'], line=dict(color='purple')), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", row=2, col=1); fig.add_hline(y=30, line_dash="dash", row=2, col=1)
elif tech_view == "KD":
    fig.add_trace(go.Scatter(x=df['Date'], y=df['K'], name='K'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['D'], name='D'), row=2, col=1)
elif tech_view == "MACD":
    fig.add_trace(go.Bar(x=df['Date'], y=df['Hist']), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD']), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['Signal']), row=2, col=1)

fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(l=20, r=20, t=10, b=20))
st.plotly_chart(fig, use_container_width=True)

# 4. 自動交易判定邏輯
if auto_active:
    row = df.iloc[-1]
    prev = df.iloc[-2]
    
    action = None
    msg = ""
    
    # 策略模擬
    if strategy == "KD 黃金交叉":
        if row['K'] > row['D'] and prev['K'] <= prev['D']:
            action = "BUY"; msg = f"KD金叉 (K:{row['K']:.1f})"
    elif strategy == "RSI 超賣反彈":
        if row['RSI'] < 30:
            action = "BUY"; msg = f"RSI超賣 ({row['RSI']:.1f})"
    
    # 隨機觸發(為了拍片效果，提高觸發率)
    if np.random.rand() > 0.9: 
        st.toast("⚡ 機器人掃描中... 發現潛在訊號", icon="🤖")
        
    if action == "BUY" and st.session_state.balance > current_p * 1000:
        # 下單
        st.session_state.balance -= current_p * 1000
        st.session_state.holdings += 1
        log = f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 自動買進 | 價格:{current_p:.1f} | 訊號:{msg}"
        st.session_state.logs.insert(0, log)
        st.toast(log, icon="✅")

# 5. 終端機日誌
st.markdown("### 📜 交易核心日誌")
log_txt = "\n".join(st.session_state.logs) if st.session_state.logs else "系統待機中... 監控市場訊號..."
st.text_area("System Log", log_txt, height=150, disabled=True)

# 自動刷新 (確保畫面一直動)
time.sleep(1.5) 
st.rerun()
