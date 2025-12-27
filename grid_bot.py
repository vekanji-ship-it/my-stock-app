import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, time as dt_time
import pytz
import requests
import feedparser

# ==========================================
# 1. 系統初始化 & CSS 風格
# ==========================================
st.set_page_config(page_title="股市特務 X - 實戰防護版", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    /* 全局風格 */
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', sans-serif; }
    
    /* 導航條 */
    .nav-bar { 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px; color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center;
    }
    .nav-title { font-size: 24px; font-weight: bold; letter-spacing: 1px; }
    .nav-user { font-size: 14px; background: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 15px; }
    
    /* 卡片容器 */
    .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px; }
    
    /* 網格表格 */
    .grid-row { padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
    .grid-active { background: #e3f2fd; border-left: 5px solid #2196f3; font-weight: bold; }
    
    /* 狀態標籤 */
    .tag-sell { background-color: #ffebee; color: #c62828; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .tag-buy { background-color: #e8f5e9; color: #2e7d32; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .tag-wait { background-color: #f5f5f5; color: #616161; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        self.name_map = {
            "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2603": "長榮", "0050": "元大台灣50",
            "0056": "元大高股息", "00878": "國泰永續高股息", "00632R": "元大台灣50反1"
        }

    def get_stock_name(self, ticker):
        clean = ticker.replace('.TW', '')
        return self.name_map.get(clean, ticker)

    @st.cache_data(ttl=30) # 縮短快取時間以獲取即時價格
    def fetch_quote(_self, ticker):
        if not ticker.endswith('.TW') and not ticker.startswith('^') and ticker.isdigit(): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period='1d', interval='1m')
            if df.empty: df = stock.history(period='5d', interval='1d')
            if df.empty: return None
            
            last = df.iloc[-1]
            price = float(last['Close'])
            change = price - df.iloc[-2]['Close'] if len(df) > 1 else 0
            pct = (change / df.iloc[-2]['Close']) * 100 if len(df) > 1 else 0
            
            return {
                "name": _self.get_stock_name(ticker.replace('.TW', '')),
                "price": price, "change": change, "pct": pct, "vol": last.get('Volume', 0),
                "open": last['Open'], "high": last['High'], "low": last['Low']
            }
        except: return None

    @st.cache_data(ttl=60)
    def fetch_kline(_self, ticker, interval="1d", period="3mo"):
        if not ticker.endswith('.TW') and not ticker.startswith('^') and ticker.isdigit(): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            df.reset_index(inplace=True)
            if 'Date' in df.columns: df['Date'] = df['Date'].dt.tz_localize(None)
            if 'Datetime' in df.columns: df['Datetime'] = df['Datetime'].dt.tz_localize(None)
            df.columns = [c.lower() for c in df.columns]
            return df
        except: return pd.DataFrame()

    def send_line_push(self, token, user_id, message):
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
        data = {"to": user_id, "messages": [{"type": "text", "text": message}]}
        try:
            requests.post(url, headers=headers, json=data)
            return True
        except: return False

engine = DataEngine()

# 繪圖函數
def plot_chart(df, title, levels=None, current_price=None, upper_limit=None, lower_limit=None):
    x_col = 'datetime' if 'datetime' in df.columns else 'date'
    fig = go.Figure(data=[go.Candlestick(
        x=df[x_col], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='K線', increasing_line_color='#d32f2f', decreasing_line_color='#2e7d32'
    )])
    
    if levels:
        for p in levels:
            fig.add_hline(y=p, line_dash="dot", line_color="rgba(100, 100, 100, 0.3)", line_width=1)
    
    if upper_limit: fig.add_hline(y=upper_limit, line_color="red", line_width=2, line_dash="dash", annotation_text="停利/上限")
    if lower_limit: fig.add_hline(y=lower_limit, line_color="green", line_width=2, line_dash="dash", annotation_text="停損/下限")
    if current_price: fig.add_hline(y=current_price, line_color="#2196f3", line_width=1.5, annotation_text="現價")

    fig.update_layout(title=title, height=450, xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=30,b=10), paper_bgcolor='white', plot_bgcolor='white')
    fig.update_xaxes(showgrid=True, gridcolor='#eee')
    fig.update_yaxes(showgrid=True, gridcolor='#eee')
    return fig

# 費用計算核心
def calculate_fee(price, qty, action, discount):
    amount = price * qty * 1000 # 總金額 (一張=1000股)
    fee_rate = 0.001425
    tax_rate = 0.003
    
    raw_fee = amount * fee_rate
    discounted_fee = int(raw_fee * discount)
    
    if action == "BUY":
        total_cost = int(amount + discounted_fee)
        return total_cost, discounted_fee, 0 # 買進無稅
    else: # SELL
        tax = int(amount * tax_rate)
        total_income = int(amount - discounted_fee - tax)
        return total_income, discounted_fee, tax

# ==========================================
# 3. Session 狀態管理
# ==========================================
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'broker_name' not in st.session_state: st.session_state.broker_name = ""
if 'user_role' not in st.session_state: st.session_state.user_role = "訪客"
if 'balance' not in st.session_state: st.session_state.balance = 500000 # 預設模擬資金
if 'fee_discount' not in st.session_state: st.session_state.fee_discount = 0.6 # 預設6折
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'line_uid' not in st.session_state: st.session_state.line_uid = ""

# ==========================================
# 4. 模組：股市情報站 (Dashboard)
# ==========================================
def render_dashboard():
    # 簡易導航條
    st.markdown(f"""
    <div class='nav-bar'>
        <span class='nav-title'>📊 股市情報站</span>
        <span class='nav-user'>👤 {st.session_state.user_role}</span>
    </div>""", unsafe_allow_html=True)
    
    col_main, col_news = st.columns([3, 2])
    with col_main:
        st.subheader("🔎 個股偵查")
        ticker = st.text_input("輸入代號", "2330")
        q = engine.fetch_quote(ticker)
        if q:
            c = "up" if q['change'] > 0 else "down"
            st.markdown(f"<h2 class='{c}'>{q['name']} {q['price']} ({q['pct']:.2f}%)</h2>", unsafe_allow_html=True)
            df = engine.fetch_kline(ticker)
            if not df.empty: st.plotly_chart(plot_chart(df, f"{ticker} 日K"), use_container_width=True)

    with col_news:
        st.subheader("📰 新聞快訊")
        st.info("系統連線正常...")

# ==========================================
# 5. 模組：網格戰神 (Grid Bot) - 升級版
# ==========================================
def render_grid_bot():
    # 1. 權限檢查
    if not st.session_state.login_status:
        st.markdown("<div class='nav-bar'><span class='nav-title'>⚡ 網格戰神 (鎖定中)</span></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.warning("🔒 此功能需要券商權限")
            broker = st.selectbox("選擇券商", ["元大證券", "凱基證券", "富邦證券"])
            pwd = st.text_input("憑證密碼", type="password")
            if st.button("🔐 安全登入", use_container_width=True):
                if pwd: # 模擬驗證
                    st.session_state.login_status = True
                    st.session_state.broker_name = broker
                    st.session_state.user_role = "VIP會員 (模擬倉)"
                    st.rerun()
                else:
                    st.error("請輸入密碼")
            st.markdown("</div>", unsafe_allow_html=True)
        return

    # 2. 已登入介面
    st.markdown(f"""
    <div class='nav-bar'>
        <div style='display:flex; flex-direction:column;'>
            <span class='nav-title'>⚡ 網格戰神 (Grid Master)</span>
            <span style='font-size:12px; opacity:0.8;'>🏦 {st.session_state.broker_name} | 模式: 當沖模擬</span>
        </div>
        <div style='text-align:right;'>
            <span class='nav-user'>👤 {st.session_state.user_role}</span><br>
            <span style='font-size:12px;'>💰 帳戶餘額: ${st.session_state.balance:,.0f}</span>
        </div>
    </div>""", unsafe_allow_html=True)

    # === 設定區 ===
    with st.expander("🔧 戰略指揮中心 (參數設定)", expanded=True):
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            st.markdown("#### 1. 標的與資金")
            ticker = st.text_input("交易代號", "00632R")
            q = engine.fetch_quote(ticker)
            cur_price = q['price'] if q else 10.0
            if q: st.success(f"現價: {cur_price}")
            
            invest_amt = st.number_input("投入金額", value=100000, step=10000)
            fee_dis = st.number_input("手續費折數 (例如2.8折輸入0.28)", value=st.session_state.fee_discount, min_value=0.1, max_value=1.0, step=0.01)
            st.session_state.fee_discount = fee_dis

        with c2:
            st.markdown("#### 2. 網格區間")
            upper = st.number_input("上限 (天花板)", value=float(cur_price * 1.05))
            lower = st.number_input("下限 (地板)", value=float(cur_price * 0.95))
            grid_num = st.number_input("網格數", value=10, min_value=2)
            shares_per_grid = int((invest_amt / grid_num) / (cur_price * 1000) * 1000) # 概算股數
            if shares_per_grid < 1: shares_per_grid = 1 # 至少1股(零股) 或 1000(整張)

        with c3:
            st.markdown("#### 3. 安全機制 (Safety)")
            st.caption("觸發時將建議全數出清")
            take_profit_pct = st.number_input("突破上限 N% 全賣 (停利)", value=2.0)
            stop_loss_pct = st.number_input("跌破下限 N% 全賣 (停損)", value=3.0)
            
            is_sim = st.toggle("啟用模擬下單模式", value=True)

    # === 計算核心 ===
    if upper > lower:
        diff = upper - lower
        step = diff / grid_num
        levels = [lower + (i * step) for i in range(grid_num + 1)]
        levels.sort(reverse=True)
        
        # 判斷安全機制狀態
        safety_msg = ""
        safety_alert = False
        
        if cur_price > upper * (1 + take_profit_pct/100):
            safety_msg = f"🚨 價格飆漲 ({cur_price}) 超過上限 {take_profit_pct}%！建議：全數停利 (ALL SELL)"
            safety_alert = True
        elif cur_price < lower * (1 - stop_loss_pct/100):
            safety_msg = f"🚨 價格崩跌 ({cur_price}) 跌破下限 {stop_loss_pct}%！建議：全數停損 (STOP LOSS)"
            safety_alert = True

        # === 顯示區 ===
        col_chart, col_list = st.columns([2, 1])
        
        with col_chart:
            st.subheader("📉 戰況圖表")
