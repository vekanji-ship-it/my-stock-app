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
# 1. 系統初始化 & 原版漂亮 CSS
# ==========================================
st.set_page_config(page_title="股市特務 X - 完美整合版", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    /* 全局設定 */
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', sans-serif; }
    
    /* 漂亮的導航條 */
    .nav-bar { 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px; color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center;
    }
    .nav-title { font-size: 24px; font-weight: bold; letter-spacing: 1px; }
    .nav-info { font-size: 14px; background: rgba(255,255,255,0.2); padding: 5px 12px; border-radius: 20px; }
    
    /* 卡片風格 */
    .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 15px; border: 1px solid #eee; }
    .grid-card { background: white; padding: 20px; border-radius: 12px; border-left: 5px solid #2196f3; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 15px; }
    
    /* 顏色與標籤 */
    .up { color: #d32f2f; font-weight: bold; } 
    .down { color: #2e7d32; font-weight: bold; }
    .tag-sell { background: #ffebee; color: #c62828; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size:12px; }
    .tag-buy { background: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size:12px; }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎 (DataEngine)
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        self.name_map = {
            "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2603": "長榮", "0050": "元大台灣50",
            "0056": "元大高股息", "00878": "國泰永續高股息", "00632R": "元大台灣50反1"
        }
        self.watch_list = ["2330", "2317", "2454", "2603", "2609", "2615", "3231", "2382", "2356", "2303", "1513", "1519"]

    def get_name(self, code):
        clean = code.replace('.TW', '')
        return self.name_map.get(clean, code)

    @st.cache_data(ttl=10)
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
            return {"name": _self.get_name(ticker.replace('.TW','')), "price": price, "change": change, "pct": pct, "vol": df.iloc[-1].get('Volume', 0)}
        except: return None

    @st.cache_data(ttl=60)
    def fetch_indices(_self):
        targets = ["^TWII", "^TWOII", "^DJI", "^IXIC", "^SOX"]
        res = {}
        for sym in targets:
            q = _self.fetch_quote(sym)
            if q: res[sym] = q # Use symbol as key temporarily
        return res

    @st.cache_data(ttl=60)
    def fetch_kline(_self, ticker, interval="1d", period="3mo"):
        if not ticker.endswith('.TW') and ticker.isdigit(): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            df.reset_index(inplace=True)
            if 'Date' in df.columns: df['Date'] = df['Date'].dt.tz_localize(None)
            if 'Datetime' in df.columns: df['Datetime'] = df['Datetime'].dt.tz_localize(None)
            df.columns = [c.lower() for c in df.columns]
            return df
        except: return pd.DataFrame()

    @st.cache_data(ttl=60)
    def scan_market(_self, strategy):
        data = []
        for c in _self.watch_list:
            q = _self.fetch_quote(c)
            if q: data.append({"代號": c, "名稱": q['name'], "現價": q['price'], "漲跌幅": q['pct'], "成交量": q['vol']})
        df = pd.DataFrame(data)
        if df.empty: return df
        if strategy == "漲幅排行 (飆股)": return df.sort_values("漲跌幅", ascending=False)
        elif strategy == "爆量強勢股": return df.sort_values("成交量", ascending=False)
        else: return df.sort_values("漲跌幅", ascending=True)

    def send_line(self, token, uid, msg):
        try:
            r = requests.post("https://api.line.me/v2/bot/message/push", 
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                json={"to": uid, "messages": [{"type": "text", "text": msg}]})
            return r.status_code == 200
        except: return False

    @st.cache_data(ttl=300)
    def get_news(_self):
        try:
            feed = feedparser.parse("https://news.google.com/rss/search?q=台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant")
            return [{"title": e.title, "link": e.link, "time": f"{e.published_parsed.tm_hour:02}:{e.published_parsed.tm_min:02}"} for e in feed.entries[:5]]
        except: return []

    def fetch_stock_profile(self, ticker): # 簡易基本面
        try:
            stock = yf.Ticker(ticker + ".TW")
            info = stock.info
            return {"pe": info.get('trailingPE'), "eps": info.get('trailingEps'), "yield": info.get('dividendYield', 0)*100}
        except: return None

engine = DataEngine()

# 繪圖
def plot_kline(df, title):
    x = df['datetime'] if 'datetime' in df.columns else df['date']
    fig = go.Figure(data=[go.Candlestick(x=x, open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#d32f2f', decreasing_line_color='#2e7d32')])
    fig.update_layout(title=title, height=350, xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=30,b=10), paper_bgcolor='white', plot_bgcolor='white')
    return fig

# 費用計算
def calc_fee(p, q, action, disc):
    amt = p * q * 1000
    fee = int(amt * 0.001425 * disc)
    tax = int(amt * 0.003) if action == "SELL" else 0
    return int(amt + fee) if action == "BUY" else int(amt - fee - tax)

# ==========================================
# 3. Session 狀態
# ==========================================
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'user_role' not in st.session_state: st.session_state.user_role = ""
if 'broker' not in st.session_state: st.session_state.broker = ""
if 'strategies' not in st.session_state: st.session_state.strategies = [] 
if 'portfolio' not in st.session_state: st.session_state.portfolio = [{"code": "2330", "name": "台積電", "cost": 900.0, "qty": 1000}]
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'line_uid' not in st.session_state: st.session_state.line_uid = ""

# ==========================================
# 4. 共用模組：小金庫 (保留功能)
# ==========================================
def render_treasury():
    st.markdown("### 💰 台股小金庫")
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    
    if st.session_state.portfolio:
        data = []
        total_p = 0
        for i in st.session_state.portfolio:
            q = engine.fetch_quote(i['code'])
            curr = q['price'] if q else i['cost']
            prof = (curr - i['cost']) * i['qty']
            total_p += prof
            data.append({"代號": i['code'], "名稱": i['name'], "成本": i['cost'], "現價": curr, "股數": i['qty'], "損益": prof})
        
        c1, c2 = st.columns([1, 3])
        c1.metric("總損益", f"${total_p:,.0f}", delta=total_p)
        c2.dataframe(pd.DataFrame(data).style.format({"成本":"{:.1f}","現價":"{:.1f}","損益":"{:.0f}"}), use_container_width=True)
    else: st.info("無庫存資料")

    tab1, tab2 = st.tabs(["➕ 新增", "🗑️ 刪除"])
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        nc = c1.text_input("代號", key="n_c")
        nn = c2.text_input("名稱", key="n_n")
        nco = c3.number_input("成本", key="n_co")
        nq = c4.number_input("股數", 1000, key="n_q")
        if st.button("加入"):
            st.session_state.portfolio.append({"code": nc, "name": nn if nn else nc, "cost": nco, "qty": nq})
            st.rerun()
    with tab2:
        if st.session_state.portfolio:
            opts = [f"{x['code']} {x['name']}" for x in st.session_state.portfolio]
            dels = st.multiselect("選擇刪除", opts)
            if st.button("確認刪除") and dels:
                st.session_state.portfolio = [x for x in st.session_state.portfolio if f"{x['code']} {x['name']}" not in dels]
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 5. 模組 A：股市情報站 (保留完整功能)
# ==========================================
def render_dashboard():
    st.markdown(f"""
    <div class='nav-bar'>
        <span class='nav-title'>📊 股市情報站</span>
        <span class='nav-info'>👤 一般會員</span>
    </div>""", unsafe_allow_html=True)

    c_main, c_side = st.columns([2.5, 1.5])
    
    with c_main:
        # 大盤
        st.subheader("🌍 市場行情")
        ind = engine.fetch_indices()
        cols = st.columns(4)
        names = ["^TWII", "^TWOII", "^DJI", "^SOX"]
        labels = ["加權", "櫃買", "道瓊", "費半"]
        for i, sym in enumerate(names):
            if sym in ind:
                q = ind[sym]
                cols[i].metric(labels[i], f"{q['price']:,.0f}", f"{q['pct']:.2f}%")
        st.divider()

        # 偵查
        st.subheader("🔎 個股偵查")
        tk = st.text_input("輸入代號", "2330")
        q = engine.fetch_quote(tk)
        
        if q:
            cc = "up" if q['change']>0 else "down"
            st.markdown(f"""
            <div class='card'>
                <h2 style='margin:0'>{q['name']} {q['price']} <span class='{cc}'>{q['change']:+.2f} ({q['pct']:+.2f}%)</span></h2>
                <small>量: {q['vol']:,}</small>
            </div>""", unsafe_allow_html=True)
            
            # K線切換
            kt = st.radio("週期", ["日K", "週K", "月K"], horizontal=True)
            kp, ki = ("3mo","1d") if kt=="日K" else ("1y","1wk") if kt=="週K" else ("5y","1mo")
            df = engine.fetch_kline(tk, kp, ki)
            if not df.empty: st.plotly_chart(plot_k
