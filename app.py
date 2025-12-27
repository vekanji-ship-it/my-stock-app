import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import twstock
import time
from datetime import datetime

# ==========================================
# 1. 頁面設定 (鉅亨風格：專業白底)
# ==========================================
st.set_page_config(page_title="ProQuant X 自動機器人", page_icon="🤖", layout="wide")

# CSS 美化：鉅亨網風格
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #333333; }
    .metric-box { border: 1px solid #e0e0e0; padding: 10px; border-radius: 5px; background: #f9f9f9; text-align: center; }
    .metric-label { font-size: 14px; color: #666; }
    .metric-value { font-size: 24px; font-weight: bold; color: #333; }
    .up { color: #eb3f38; }
    .down { color: #2daa59; }
    
    /* 側邊欄樣式 */
    [data-testid="stSidebar"] { background-color: #f4f6f9; border-right: 1px solid #ddd; }
    
    /* 交易日誌區塊 */
    .log-container { 
        height: 200px; overflow-y: scroll; 
        background-color: #1e1e1e; color: #00ff00; 
        font-family: 'Courier New', monospace; padding: 10px; border-radius: 5px; 
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心大腦：技術指標計算引擎
# ==========================================
class TechIndicators:
    @staticmethod
    def calculate(df):
        # 1. 移動平均線 (MA)
        df['MA5'] = df['close'].rolling(window=5).mean()
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA60'] = df['close'].rolling(window=60).mean()

        # 2. RSI (相對強弱指標)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # 3. KD (隨機指標)
        low_min = df['low'].rolling(window=9).min()
        high_max = df['high'].rolling(window=9).max()
        df['RSV'] = (df['close'] - low_min) / (high_max - low_min) * 100
        df['K'] = df['RSV'].ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()

        # 4. MACD
        exp12 = df['close'].ewm(span=12, adjust=False).mean()
        exp26 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp12 - exp26
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['Hist'] = df['MACD'] - df['Signal']
        
        return df

# ==========================================
# 3. 數據源與機器人邏輯
# ==========================================
if 'bot_log' not in st.session_state:
    st.session_state.bot_log = []
if 'balance' not in st.session_state:
    st.session_state.balance = 1000000 # 初始資金 100萬
if 'holdings' not in st.session_state:
    st.session_state.holdings = 0

def get_data(stock_id):
    try:
        stock = twstock.Stock(stock_id)
        # 抓取歷史數據
        data = stock.fetch_from(2024, 10)
        df = pd.DataFrame(data)
        df['Date'] = pd.to_datetime(df['date'])
        
        # 抓取即時數據 (讓指標會跳動)
        real = twstock.realtime.get(stock_id)
        if real['success']:
            latest_price = float(real['realtime']['latest_trade_price'])
            # 將即時價格追加到歷史數據最後一筆，模擬即時運算
            new_row = df.iloc[-1].copy()
            new_row['close'] = latest_price
            new_row['Date'] = pd.Timestamp.now()
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
        return TechIndicators.calculate(df), real
    except:
        return pd.DataFrame(), None

# ==========================================
# 4. 介面佈局
# ==========================================

# --- Sidebar: 機器人控制台 ---
with st.sidebar:
    st.title("🤖 機器人控制台")
    target_stock = st.text_input("監控代號", "2330")
    
    st.divider()
    st.subheader("⚙️ 策略設定")
    strategy_mode = st.selectbox("選擇自動交易策略", 
        ["RSI 超賣反彈 (RSI < 30)", "KD 黃金交叉 (K > D)", "MACD 趨勢突破", "手動模式"])
    
    auto_trade = st.toggle("🔴 啟動自動下單", value=False)
    
    st.divider()
    st.subheader("📊 技術指標顯示")
    show_ma = st.checkbox("顯示均線 (MA)", value=True)
    indicator_panel = st.radio("副圖指標", ["成交量", "RSI", "KD", "MACD"])

# --- Main: 戰情室 ---
df, real_data = get_data(target_stock)

if not df.empty and real_data:
    current_price = df['close'].iloc[-1]
    last_close = df['close'].iloc[-2]
    change = current_price - last_close
    color_cls = "up" if change > 0 else "down"
    
    # 1. 頂部大數據
    c1, c2, c3, c4 = st.columns([2, 2, 2, 4])
    with c1:
        st.markdown(f"## {target_stock}")
    with c2:
        st.markdown(f"<h2 class='{color_cls}'>{current_price:.2f}</h2>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<h4 class='{color_cls}'>{change:+.2f} ({change/last_close*100:+.2f}%)</h4>", unsafe_allow_html=True)
    with c4:
        st.markdown(f"**資金餘額**: ${st.session_state.balance:,.0f} | **庫存**: {st.session_state.holdings} 張")

    st.divider()

    # 2. 專業線圖 (Plotly)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_width=[0.3, 0.7])

    # 主圖：K線 + MA
    fig.add_trace(go.Candlestick(x=df['Date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'), row=1, col=1)
    
    if show_ma:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA5'], line=dict(color='orange', width=1), name='MA5'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], line=dict(color='blue', width=1), name='MA20'), row=1, col=1)

    # 副圖：根據選擇顯示
    if indicator_panel == "成交量":
        fig.add_trace(go.Bar(x=df['Date'], y=df['capacity'], name='Volume', marker_color='#999'), row=2, col=1)
    elif indicator_panel == "RSI":
        fig.add_trace(go.Scatter(x=df['Date'], y=df['RSI'], line=dict(color='purple'), name='RSI'), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    elif indicator_panel == "KD":
        fig.add_trace(go.Scatter(x=df['Date'], y=df['K'], line=dict(color='orange'), name='K'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['D'], line=dict(color='blue'), name='D'), row=2, col=1)
    elif indicator_panel == "MACD":
        fig.add_trace(go.Bar(x=df['Date'], y=df['Hist'], name='Hist'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], line=dict(color='orange'), name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['Signal'], line=dict(color='blue'), name='Signal'), row=2, col=1)

    fig.update_layout(height=600, xaxis_rangeslider_visible=False, plot_bgcolor='white', margin=dict(l=50, r=20, t=10, b=20))
    fig.update_xaxes(showgrid=True, gridcolor='#f0f0f0')
    fig.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
    
    st.plotly_chart(fig, use_container_width=True)

    # 3. 機器人自動執行邏輯
    if auto_trade:
        last_rsi = df['RSI'].iloc[-1]
        last_k = df['K'].iloc[-1]
        last_d = df['D'].iloc[-1]
        
        signal = None
        reason = ""
        
        # 策略判斷
        if strategy_mode == "RSI 超賣反彈 (RSI < 30)":
            if last_rsi < 30:
                signal = "BUY"
                reason = f"RSI 數值 {last_rsi:.1f} 進入超賣區"
            elif last_rsi > 70 and st.session_state.holdings > 0:
                signal = "SELL"
                reason = f"RSI 數值 {last_rsi:.1f} 進入超買區"
                
        elif strategy_mode == "KD 黃金交叉 (K > D)":
            if last_k > last_d and df['K'].iloc[-2] <= df['D'].iloc[-2]: # 剛交叉
                signal = "BUY"
                reason = f"KD 黃金交叉 (K={last_k:.1f}, D={last_d:.1f})"
        
        # 執行交易 & 寫入日誌
        t = datetime.now().strftime("%H:%M:%S")
        
        # 為了展示效果，我們隨機偶爾觸發一下 (拍片用)
        # 實戰中請把下面這行 random 註解掉
        if np.random.rand() > 0.8: 
            st.toast("⚡ 機器人正在掃描市場訊號...", icon="🔍")
        
        if signal == "BUY" and st.session_state.balance >= current_price * 1000:
            st.session_state.balance -= current_price * 1000
            st.session_state.holdings += 1
            log_msg = f"[{t}] ✅ 買進執行 | {target_stock} | 價格: {current_price} | 原因: {reason}"
            st.session_state.bot_log.insert(0, log_msg)
            st.toast(log_msg, icon="✅")
            
        elif signal == "SELL" and st.session_state.holdings > 0:
            st.session_state.balance += current_price * 1000
            st.session_state.holdings -= 1
            log_msg = f"[{t}] 🚀 賣出執行 | {target_stock} | 價格: {current_price} | 原因: {reason}"
            st.session_state.bot_log.insert(0, log_msg)
            st.toast(log_msg, icon="🚀")

    # 4. 顯示終端機日誌 (Hacker Style)
    st.subheader("📜 機器人執行日誌 (System Log)")
    log_text = "\n".join(st.session_state.bot_log) if st.session_state.bot_log else "等待訊號中... 系統監控中..."
    st.text_area("Console", value=log_text, height=200, disabled=True)
    
    # 自動刷新機制
    time.sleep(2)
    st.rerun()

else:
    st.warning("正在連線證交所與計算指標... 請稍候")
    time.sleep(1)
    st.rerun()
