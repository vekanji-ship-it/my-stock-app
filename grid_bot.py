import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime
import pytz
import requests
import feedparser

# ==========================================
# 1. 系統設定
# ==========================================
st.set_page_config(page_title="股市特務 X - 絕對修正版", page_icon="🔥", layout="wide")

# CSS 優化 (移除可能導致跑版的部分)
st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; }
    .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
    .status-tag { padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; }
    .tag-sell { background: #ffebee; color: #c62828; }
    .tag-buy { background: #e8f5e9; color: #2e7d32; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 數據引擎
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')

    @st.cache_data(ttl=10) # 縮短快取以確保即時性
    def fetch_quote(_self, ticker):
        if not ticker.endswith('.TW') and ticker.isdigit(): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period='1d', interval='1m')
            if df.empty: df = stock.history(period='5d', interval='1d')
            if df.empty: return None
            price = float(df.iloc[-1]['Close'])
            change = price - df.iloc[-2]['Close'] if len(df) > 1 else 0
            pct = (change / df.iloc[-2]['Close']) * 100 if len(df) > 1 else 0
            return {"name": ticker, "price": price, "change": change, "pct": pct, "vol": df.iloc[-1].get('Volume', 0)}
        except: return None

    @st.cache_data(ttl=60)
    def fetch_kline(_self, ticker, period="1mo", interval="60m"):
        if not ticker.endswith('.TW') and ticker.isdigit(): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            df.reset_index(inplace=True)
            if 'Datetime' in df.columns: df['Datetime'] = df['Datetime'].dt.tz_localize(None)
            if 'Date' in df.columns: df['Date'] = df['Date'].dt.tz_localize(None)
            df.columns = [c.lower() for c in df.columns]
            return df
        except: return pd.DataFrame()
    
    def send_line(self, token, uid, msg):
        try:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
            payload = {"to": uid, "messages": [{"type": "text", "text": msg}]}
            r = requests.post(url, headers=headers, json=payload)
            return r.status_code == 200
        except: return False

engine = DataEngine()

# ==========================================
# 3. Session 初始化
# ==========================================
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_tier' not in st.session_state: st.session_state.user_tier = "一般會員"
if 'grid_strategies' not in st.session_state: st.session_state.grid_strategies = [] # 儲存網格策略
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'line_uid' not in st.session_state: st.session_state.line_uid = ""

# ==========================================
# 4. 關鍵功能：登入與權限
# ==========================================
TIER_LIMITS = {
    "一般會員": 1,
    "小資會員": 3,
    "大佬會員": 5
}

def login_screen():
    st.markdown("## 🔒 網格戰神 - 登入")
    st.info("請先進行模擬登入以解鎖功能")
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        broker = col1.selectbox("券商", ["元大", "凱基", "富邦"])
        # 這裡就是你要的會員選擇功能
        tier = col2.selectbox("選擇會員等級 (模擬)", ["一般會員", "小資會員", "大佬會員"])
        
        acc = st.text_input("帳號", placeholder="任意輸入")
        pwd = st.text_input("密碼", type="password", placeholder="任意輸入")
        
        if st.button("🚀 登入系統", use_container_width=True):
            if pwd:
                st.session_state.logged_in = True
                st.session_state.user_tier = tier
                st.session_state.broker = broker
                st.rerun()
            else:
                st.error("請輸入密碼")

# ==========================================
# 5. 網格戰神主程式
# ==========================================
def render_grid_bot():
    # === 1. 強制檢查登入 ===
    if not st.session_state.logged_in:
        login_screen()
        return

    # === 2. 登入後畫面 ===
    limit = TIER_LIMITS[st.session_state.user_tier]
    current_count = len(st.session_state.grid_strategies)
    
    # 頂部狀態列
    c1, c2, c3 = st.columns([2, 1, 1])
    c1.markdown(f"### ⚡ 網格戰神 | {st.session_state.broker}")
    c2.markdown(f"**{st.session_state.user_tier}**")
    c3.metric("額度使用", f"{current_count} / {limit}")
    
    st.divider()

    # === 3. 新增策略區 (如果沒滿額度) ===
    if current_count < limit:
        with st.expander("➕ 新增網格策略", expanded=True):
            c_in1, c_in2, c_in3, c_in4 = st.columns(4)
            t_code = c_in1.text_input("代號", "0050")
            t_upper = c_in2.number_input("上限", value=200.0)
            t_lower = c_in3.number_input("下限", value=150.0)
            t_grids = c_in4.number_input("格數", value=10, step=1)
            
            if st.button("💾 儲存監控"):
                st.session_state.grid_strategies.append({
                    "code": t_code, "upper": t_upper, "lower": t_lower, "grids": t_grids,
                    "active": True
                })
                st.rerun()
    else:
        st.warning(f"⚠️ 已達 {st.session_state.user_tier} 額度上限 ({limit}筆)，請升級或刪除舊策略。")

    # === 4. 監控列表展示 (重點功能) ===
    st.markdown("### 📋 監控中策略")
    
    # LINE 設定 (放在這裡確保看得到)
    with st.expander("📢 LINE 通知設定 (全域)", expanded=False):
        st.session_state.line_token = st.text_input("Token", st.session_state.line_token, type="password")
        st.session_state.line_uid = st.text_input("UID", st.session_state.line_uid)

    for i, strategy in enumerate(st.session_state.grid_strategies):
        # 每一筆資料一個卡片
        with st.container(border=True):
            c_info, c_act = st.columns([3, 1])
            
            # 抓即時價
            q = engine.fetch_quote(strategy['code'])
            cur_p = q['price'] if q else 0.0
            
            with c_info:
                st.subheader(f"{strategy['code']} (現價: {cur_p})")
                st.text(f"區間: {strategy['lower']} ~ {strategy['upper']} | 格數: {strategy['grids']}")
                
                # 簡易網格表計算
                step = (strategy['upper'] - strategy['lower']) / strategy['grids']
                levels = [strategy['lower'] + x*step for x in range(strategy['grids']+1)]
                
                # 判斷最近的掛單
                near_sell = min([p for p in levels if p > cur_p], default=None)
                near_buy = max([p for p in levels if p < cur_p], default=None)
                
                c_a, c_b = st.columns(2)
                if near_sell: c_a.error(f"上方賣壓: {near_sell:.2f}")
                if near_buy: c_b.success(f"下方支撐: {near_buy:.2f}")

            with c_act:
                if st.button(f"🗑️ 刪除 #{i+1}", key=f"del_{i}"):
                    st.session_state.grid_strategies.pop(i)
                    st.rerun()
                
                # LINE 通知按鈕 (你要的功能)
                if st.button(f"📤 發送通知 #{i+1}", key=f"line_{i}"):
                    if st.session_state.line_token:
                        msg = f"【網格快報】\n{strategy['code']} 現價: {cur_p}\n接近賣點: {near_sell}\n接近買點: {near_buy}"
                        if engine.send_line(st.session_state.line_token, st.session_state.line_uid, msg):
                            st.toast("已發送通知", icon="✅")
                        else:
                            st.toast("發送失敗", icon="❌")
                    else:
                        st.error("請先設定 Token")

# ==========================================
# 6. 股市情報站 (保留基本功能)
# ==========================================
def render_dashboard():
    st.title("📊 股市情報站")
    st.info("這裡提供基本的查價與K線功能")
    tk = st.text_input("查詢代號", "2330")
    if st.button("查詢"):
        q = engine.fetch_quote(tk)
        if q:
            st.metric(tk, q['price'], f"{q['pct']:.2f}%")
            df = engine.fetch_kline(tk)
            if not df.empty:
                fig = go.Figure(data=[go.Candlestick(x=df['datetime'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
                st.plotly_chart(fig)

# ==========================================
# 7. 側邊導航與登出
# ==========================================
with st.sidebar:
    st.title("🚀 導航")
    
    if st.session_state.logged_in:
        st.success(f"Hi, {st.session_state.user_tier}")
        if st.button("登出"):
            st.session_state.logged_in = False
            st.session_state.grid_strategies = [] # 登出清空
            st.rerun()
    
    page = st.radio("前往", ["⚡ 網格戰神", "📊 股市情報站"])

if page == "⚡ 網格戰神":
    render_grid_bot()
elif page == "📊 股市情報站":
    render_dashboard()
