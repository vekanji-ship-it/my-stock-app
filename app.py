import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import twstock
import time
from datetime import datetime

# ==========================================
# 1. App 級別設定 (Sanju Style)
# ==========================================
st.set_page_config(page_title="SanjuBot", page_icon="📱", layout="centered") 
# 注意：layout 改成 centered，模擬手機窄螢幕

# 🎨 CSS 黑魔法：強制轉型成 App 介面
st.markdown("""
    <style>
    /* 1. 全局設定：三竹黑 */
    .stApp { background-color: #000000; color: #ffffff; }
    
    /* 2. 隱藏 Streamlit 原生元素 (漢堡選單、Footer) */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* 3. 報價頭部樣式 */
    .sanju-header {
        position: fixed;
        top: 0; left: 0; right: 0;
        background-color: #1a1a1a;
        padding: 10px 15px;
        z-index: 999;
        border-bottom: 1px solid #333;
        display: flex; justify-content: space-between; align-items: center;
    }
    .stock-name { font-size: 20px; font-weight: bold; color: #fff; }
    .stock-id { font-size: 14px; color: #aaa; margin-left: 5px; }
    
    /* 4. 價格顏色定義 (台股紅漲綠跌) */
    .p-up { color: #ff333a !important; }
    .p-down { color: #00ff00 !important; }
    .p-flat { color: #ffffff !important; }
    
    /* 5. 底部導航列 (App 的靈魂) */
    .bottom-nav {
        position: fixed;
        bottom: 0; left: 0; right: 0;
        background-color: #1a1a1a;
        height: 60px;
        display: flex; justify-content: space-around; align-items: center;
        border-top: 1px solid #333;
        z-index: 999;
    }
    .nav-item {
        color: #888; text-align: center; font-size: 10px; cursor: pointer; flex: 1;
    }
    .nav-item:hover { color: #ff9900; }
    .nav-icon { font-size: 20px; display: block; margin-bottom: 2px; }
    
    /* 6. 五檔報價樣式 */
    .order-book-row {
        display: flex; justify-content: space-between;
        padding: 4px 8px; border-bottom: 1px solid #222; font-family: monospace; font-size: 14px;
    }
    .bid-bg { background-color: rgba(255, 51, 58, 0.1); }
    .ask-bg { background-color: rgba(0, 255, 0, 0.1); }

    /* 調整主要內容區塊，避免被 Header/Footer 遮住 */
    .block-container { padding-top: 70px; padding-bottom: 80px; }
    
    /* 按鈕美化 */
    .stButton>button {
        width: 100%; border-radius: 0; background-color: #333; color: white; border: 1px solid #555;
    }
    .stButton>button:hover { border-color: #ff9900; color: #ff9900; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 模擬後端數據 (為了流暢度先用模擬)
# ==========================================
if 'nav_selection' not in st.session_state:
    st.session_state.nav_selection = "報價"

def get_sanju_data(stock_id):
    # 這裡可以用 twstock.realtime.get(stock_id) 替換
    base = 1000.0
    noise = np.random.normal(0, 1)
    price = base + noise
    change = noise
    return {
        "id": stock_id, "name": "台積電",
        "price": price, "change": change, "pct": change/base*100,
        "volume": 23456, "open": 998, "high": 1005, "low": 990,
        "bids": [(price-i, np.random.randint(1,50)) for i in range(1,6)],
        "asks": [(price+i, np.random.randint(1,50)) for i in range(1,6)]
    }

data = get_sanju_data("2330")

# ==========================================
# 3. 介面佈局 (Mobile Layout)
# ==========================================

# --- A. 頂部固定 Header (模擬 App Title Bar) ---
color_cls = "p-up" if data['change'] > 0 else "p-down"
sign = "▲" if data['change'] > 0 else "▼"

st.markdown(f"""
    <div class="sanju-header">
        <div>
            <span class="stock-name">{data['name']}</span>
            <span class="stock-id">{data['id']}</span>
        </div>
        <div style="text-align:right;">
            <div style="font-size:24px; font-weight:bold;" class="{color_cls}">{data['price']:.0f}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- B. 內容區域 (根據底部選單切換) ---

if st.session_state.nav_selection == "報價":
    # 1. 資訊列
    c1, c2, c3 = st.columns(3)
    c1.metric("漲跌", f"{sign}{abs(data['change']):.1f}")
    c2.metric("幅度", f"{sign}{abs(data['pct']):.2f}%")
    c3.metric("總量", f"{data['volume']}")
    
    st.markdown("---")
    
    # 2. 技術線圖 (K線)
    st.markdown("###### 📈 技術線圖")
    # 模擬K線數據
    dates = pd.date_range(end=datetime.now(), periods=30)
    df = pd.DataFrame(index=dates)
    df['Close'] = np.random.normal(1000, 10, 30).cumsum() + 1000
    df['Open'] = df['Close'].shift(1)
    df['High'] = df[['Open', 'Close']].max(axis=1) + 2
    df['Low'] = df[['Open', 'Close']].min(axis=1) - 2
    
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                         increasing_line_color='#ff333a', decreasing_line_color='#00ff00')])
    fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='black', plot_bgcolor='black',
                      xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#333'))
    st.plotly_chart(fig, use_container_width=True)
    
    # 3. 五檔 (模擬三竹樣式)
    st.markdown("###### 📑 最佳五檔")
    c_ask, c_bid = st.columns(2)
    
    with c_ask:
        st.markdown("<div style='text-align:center; color:#00ff00; border-bottom:1px solid #333'>賣出 (Ask)</div>", unsafe_allow_html=True)
        for p, v in data['asks'][::-1]:
            st.markdown(f"""<div class='order-book-row ask-bg'><span class='p-down'>{p:.0f}</span><span>{v}</span></div>""", unsafe_allow_html=True)
            
    with c_bid:
        st.markdown("<div style='text-align:center; color:#ff333a; border-bottom:1px solid #333'>買進 (Bid)</div>", unsafe_allow_html=True)
        for p, v in data['bids']:
            st.markdown(f"""<div class='order-book-row bid-bg'><span class='p-up'>{p:.0f}</span><span>{v}</span></div>""", unsafe_allow_html=True)

elif st.session_state.nav_selection == "下單":
    st.markdown("#### ⚡ 快速下單")
    col_Type = st.radio("交易類別", ["現股", "當沖", "零股"], horizontal=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.number_input("價格", value=1000.0, step=0.5)
    with c2:
        st.number_input("數量 (張)", value=1, step=1)
        
    b1, b2 = st.columns(2)
    if b1.button("🔴 買進", use_container_width=True):
        st.toast("委託成功：買進送出", icon="✅")
    if b2.button("🟢 賣出", use_container_width=True):
        st.toast("委託成功：賣出送出", icon="✅")

elif st.session_state.nav_selection == "庫存":
    st.markdown("#### 🎒 我的庫存")
    st.info("目前持有：2330 台積電 (2張)")
    st.metric("未實現損益", "+$23,000", delta_color="normal")
    
    st.table(pd.DataFrame({
        "股票": ["台積電", "鴻海"],
        "成本": [900, 150],
        "現價": [1000, 160],
        "損益": ["+20000", "+10000"]
    }))

# --- C. 底部導航列 (Fake Bottom Navigation) ---
# 利用 Streamlit 的 button 模擬點擊切換
st.markdown("---") # 墊高底部
c1, c2, c3, c4 = st.columns(4)

# 這裡是一個 Hack，用來模擬底部選單點擊
# 注意：為了美觀，我們用上面的 CSS 畫了假的 bar，但實際互動我們用下面的按鈕
with st.container():
    st.write("") # 佔位

# 實際上 Streamlit 很難做到底部固定按鈕，所以我們用 radio 在上方切換最穩
# 但為了滿足你的要求，我們用這種變通方式：
st.markdown("""
<div class="bottom-nav">
    <div class="nav-item">📈<br>報價</div>
    <div class="nav-item">⚡<br>下單</div>
    <div class="nav-item">🎒<br>庫存</div>
    <div class="nav-item">⚙️<br>設定</div>
</div>
""", unsafe_allow_html=True)

# 真正的切換開關 (為了展示效果，我們先放上面，或者你可以用 sidebar)
# 這裡為了展示「像三竹」，我把切換放在最上面比較合理
st.sidebar.title("App 導航")
selection = st.sidebar.radio("切換頁面", ["報價", "下單", "庫存"])
st.session_state.nav_selection = selection