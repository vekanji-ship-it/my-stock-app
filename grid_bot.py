import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import requests
from datetime import datetime
import pytz

# 避免 feedparser 造成白屏
try:
    import feedparser
except ImportError:
    feedparser = None

# ==========================================
# 1. 系統設定 (System Config)
# ==========================================
st.set_page_config(page_title="股市特務 X - 雙模組整合版", page_icon="🔥", layout="wide")

# CSS: 整合您原本喜歡的藍色風格 + 網格戰神需要的樣式
st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', sans-serif; }
    
    /* 導航條 */
    .nav-bar { 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px; color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    
    /* 卡片容器 */
    .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px; }
    
    /* 網格戰神專用卡片 */
    .bot-card { border-left: 5px solid #ff9800; background: white; padding: 20px; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
    
    /* 顏色 */
    .up { color: #d32f2f; font-weight: bold; } 
    .down { color: #2e7d32; font-weight: bold; }
    
    /* 按鈕微調 */
    .stButton>button { width: 100%; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎 (Data Engine)
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        # 模擬觀察名單
        self.watch_list = ["2330", "2317", "2454", "2603", "0050", "00632R", "2609", "2615", "1513"]

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
            return {"name": ticker.replace('.TW',''), "price": price, "change": change, "pct": pct, "vol": df.iloc[-1].get('Volume', 0)}
        except: return None

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

    # 模擬掃描 (股市情報站用)
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

    # LINE 通知 (網格戰神用)
    def send_line(self, token, uid, msg):
        try:
            r = requests.post("https://api.line.me/v2/bot/message/push", 
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                json={"to": uid, "messages": [{"type": "text", "text": msg}]})
            return r.status_code == 200
        except: return False

    @st.cache_data(ttl=300)
    def get_news(_self):
        if not feedparser: return []
        try:
            feed = feedparser.parse("https://news.google.com/rss/search?q=台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant")
            return [{"title": e.title, "link": e.link, "time": "最新"} for e in feed.entries[:5]]
        except: return []

    def fetch_profile(self, ticker):
        if not ticker.endswith('.TW') and ticker.isdigit(): ticker += '.TW'
        try:
            info = yf.Ticker(ticker).info
            return {"pe": info.get('trailingPE'), "eps": info.get('trailingEps'), "yield": info.get('dividendYield', 0)*100}
        except: return None

engine = DataEngine()

# 繪圖工具
def plot_kline(df, title):
    x = df['datetime'] if 'datetime' in df.columns else df['date']
    fig = go.Figure(data=[go.Candlestick(x=x, open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#d32f2f', decreasing_line_color='#2e7d32')])
    fig.update_layout(title=title, height=350, xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=30,b=10), paper_bgcolor='white', plot_bgcolor='white')
    return fig

# 網格費用計算
def calc_fee(p, q, action, disc):
    amt = p * q * 1000
    fee = int(amt * 0.001425 * disc)
    tax = int(amt * 0.003) if action == "SELL" else 0
    return int(amt + fee) if action == "BUY" else int(amt - fee - tax)

# ==========================================
# 3. Session 狀態管理 (關鍵：解決衝突)
# ==========================================
# 股市情報站專用
if 'portfolio' not in st.session_state: st.session_state.portfolio = [{"code": "2330", "name": "台積電", "cost": 900.0, "qty": 1000}]

# 網格戰神專用
if 'grid_login' not in st.session_state: st.session_state.grid_login = False
if 'member_tier' not in st.session_state: st.session_state.member_tier = "一般會員"
if 'grid_broker' not in st.session_state: st.session_state.grid_broker = ""
if 'strategies' not in st.session_state: st.session_state.strategies = [] 
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'line_uid' not in st.session_state: st.session_state.line_uid = ""

# ==========================================
# 4. 模組 A：股市情報站 (Dashboard) - 您要的原本樣貌
# ==========================================
def render_dashboard():
    st.markdown("<div class='nav-bar'><span class='nav-title'>📊 股市情報站</span></div>", unsafe_allow_html=True)
    
    col_main, col_news = st.columns([3, 1.5])
    
    with col_main:
        # 1. 偵查
        st.subheader("🔎 全方位個股偵查")
        tk = st.text_input("輸入代號", "2330")
        q = engine.fetch_quote(tk)
        
        if q:
            c = "up" if q['change']>0 else "down"
            st.markdown(f"<div class='card'><h2>{q['name']} {q['price']} <span class='{c}'>{q['change']:+.2f} ({q['pct']:+.2f}%)</span></h2></div>", unsafe_allow_html=True)
            
            # K線圖 (日/週/月)
            kt = st.radio("週期", ["日K", "週K", "月K"], horizontal=True)
            kp, ki = ("3mo","1d") if kt=="日K" else ("1y","1wk") if kt=="週K" else ("5y","1mo")
            df = engine.fetch_kline(tk, kp, ki)
            if not df.empty: st.plotly_chart(plot_kline(df, f"{tk} {kt}"), use_container_width=True)
            
            # 基本面
            prof = engine.fetch_profile(tk)
            if prof:
                c1, c2, c3 = st.columns(3)
                c1.metric("本益比", f"{prof['pe']:.2f}" if prof['pe'] else "-")
                c2.metric("EPS", f"{prof['eps']:.2f}" if prof['eps'] else "-")
                c3.metric("殖利率", f"{prof['yield']:.2f}%" if prof['yield'] else "-")
            
            st.link_button("鉅亨網詳情", f"https://stock.cnyes.com/market/TWS:{tk}:STOCK")
        
        st.divider()
        
        # 2. 熱點掃描 (您的截圖功能)
        st.subheader("🔥 市場熱點排行 (Scanner)")
        st.info("💡 請設定條件以開始搜尋")
        c1, c2, c3, c4 = st.columns([2, 2, 3, 2])
        c1.number_input("最低價", 10)
        c2.number_input("最高價", 1000)
        strat = c3.selectbox("篩選策略", ["漲跌停 (±10%)", "爆量強勢股", "飆股 (漲幅排行)"])
        if c4.button("🔍 開始掃描", type="primary"):
            res = engine.scan_market(strat)
            st.dataframe(res, use_container_width=True)

        st.divider()

        # 3. 資產庫存 (您的截圖功能)
        st.subheader("🎒 我的資產庫存")
        with st.expander("➕ 新增庫存紀錄"):
            c1, c2, c3, c4 = st.columns(4)
            pc = c1.text_input("代號", key="pc")
            pn = c2.text_input("名稱", key="pn")
            pco = c3.number_input("成本", key="pco")
            pq = c4.number_input("股數", 1000, key="pq")
            if st.button("加入"):
                st.session_state.portfolio.append({"code":pc, "name":pn, "cost":pco, "qty":pq})
                st.rerun()
        
        if st.session_state.portfolio:
            p_data = []
            for i in st.session_state.portfolio:
                curr = engine.fetch_quote(i['code'])
                price = curr['price'] if curr else i['cost']
                prof = (price - i['cost']) * i['qty']
                p_data.append({"代號": i['code'], "名稱": i['name'], "持有": i['qty'], "成本": i['cost'], "現價": price, "損益": prof})
            st.dataframe(pd.DataFrame(p_data), use_container_width=True)

    with col_news:
        st.subheader("📰 新聞快訊")
        news = engine.get_news()
        if news:
            for n in news:
                st.markdown(f"<div style='border-bottom:1px solid #eee; padding:5px'><a href='{n['link']}'>{n['title']}</a><br><small>{n['time']}</small></div>", unsafe_allow_html=True)
        else:
            st.info("新聞載入中...")

# ==========================================
# 5. 模組 B：當沖網格戰神 (Grid Bot) - 全新替換版
# ==========================================
def render_grid_bot():
    TIER_LIMITS = {"一般會員": 1, "小資會員": 3, "大佬會員": 5}

    # === 1. 模擬登入畫面 (您的截圖功能) ===
    if not st.session_state.grid_login:
        st.markdown("<br><br>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("<div class='card' style='text-align:center;'>", unsafe_allow_html=True)
            st.subheader("🔒 模擬登入系統")
            st.info("請先登入以使用當沖網格功能")
            
            with st.form("grid_login"):
                bk = st.selectbox("選擇模擬券商", ["元大證券", "凱基證券", "富邦證券"])
                role = st.selectbox("會員等級", ["一般會員", "小資會員", "大佬會員"])
                st.text_input("帳號 (任意輸入)")
                pwd = st.text_input("密碼 (任意輸入)", type="password")
                
                if st.form_submit_button("🚀 登入"):
                    if pwd:
                        st.session_state.grid_login = True
                        st.session_state.member_tier = role
                        st.session_state.grid_broker = bk
                        st.rerun()
                    else: st.error("請輸入密碼")
            st.markdown("</div>", unsafe_allow_html=True)
        return

    # === 2. 登入後畫面 (新功能區) ===
    limit = TIER_LIMITS[st.session_state.member_tier]
    used = len(st.session_state.strategies)
    
    st.markdown(f"""
    <div class='nav-bar'>
        <span class='nav-title'>⚡ 當沖網格戰神 | {st.session_state.grid_broker}</span>
        <span style='float:right; margin-top:5px; color:white;'>
            👤 {st.session_state.member_tier} (額度: {used}/{limit})
        </span>
    </div>""", unsafe_allow_html=True)

    # LINE Token 設定
    with st.expander("📢 LINE 通知設定", expanded=False):
        c1, c2 = st.columns(2)
        st.session_state.line_token = c1.text_input("Token", st.session_state.line_token, type="password")
        st.session_state.line_uid = c2.text_input("User ID", st.session_state.line_uid)

    # 新增策略 (受會員等級限制)
    if used < limit:
        with st.expander("➕ 新增網格監控", expanded=True):
            with st.form("add_strat"):
                c1, c2, c3, c4, c5 = st.columns(5)
                code = c1.text_input("代號", "00632R")
                upper = c2.number_input("上限", 100.0)
                lower = c3.number_input("下限", 80.0)
                grids = c4.number_input("格數", 10, min_value=2)
                disc = c5.number_input("折數", 0.6)
                if st.form_submit_button("💾 加入"):
                    st.session_state.strategies.append({"code": code, "upper": upper, "lower": lower, "grids": grids, "disc": disc})
                    st.rerun()
    else:
        st.warning(f"⚠️ 您的 {st.session_state.member_tier} 額度已滿 ({limit}筆)")

    # 監控列表
    st.markdown("### 📋 監控中列表")
    if not st.session_state.strategies: st.info("目前無監控策略，請上方新增")

    for i, s in enumerate(st.session_state.strategies):
        with st.container():
            st.markdown("<div class='bot-card'>", unsafe_allow_html=True)
            c_info, c_act = st.columns([3, 1])
            
            # 計算
            q = engine.fetch_quote(s['code'])
            curr = q['price'] if q else 0
            step = (s['upper'] - s['lower']) / s['grids']
            levels = [s['lower'] + x * step for x in range(s['grids'] + 1)]
            near_s = min([p for p in levels if p > curr], default=None)
            near_b = max([p for p in levels if p < curr], default=None)

            with c_info:
                st.markdown(f"**{s['code']} (現價: {curr})**")
                st.caption(f"區間: {s['lower']}~{s['upper']} | 格數: {s['grids']}")
                c1, c2 = st.columns(2)
                if near_s: c1.markdown(f"<span style='color:red'>🔴 賣壓: {near_s:.2f}</span>", unsafe_allow_html=True)
                if near_b: c2.markdown(f"<span style='color:green'>🟢 支撐: {near_b:.2f}</span>", unsafe_allow_html=True)

            with c_act:
                if st.button("🗑️ 刪除", key=f"del_{i}"):
                    st.session_state.strategies.pop(i)
                    st.rerun()
                
                # LINE 通知按鈕
                if st.button("📤 Line 通知", key=f"ln_{i}"):
                    if st.session_state.line_token:
                        fb = calc_fee(near_b or 0, 1, "BUY", s['disc'])
                        fs = calc_fee(near_s or 0, 1, "SELL", s['disc'])
                        msg = f"【網格快報】{s['code']} 現價:{curr} 買:${fb} 賣:${fs}"
                        if engine.send_line(st.session_state.line_token, st.session_state.line_uid, msg):
                            st.toast("發送成功", icon="✅")
                        else: st.error("發送失敗")
                    else: st.error("請輸入 Token")
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 6. 主程式導航 (含登出按鈕)
# ==========================================
with st.sidebar:
    st.title("🕵️ 股市特務 X")
    st.markdown("---")
    
    # 這裡就是關鍵的「登出」按鈕，解決您看不到登入畫面的問題
    if st.session_state.grid_login:
        st.success(f"已登入: {st.session_state.member_tier}")
        if st.button("登出 (切換帳號)", type="primary"):
            st.session_state.grid_login = False
            st.session_state.strategies = []
            st.rerun()

    module = st.radio("導航", ["📊 股市情報站", "⚡ 當沖網格戰神"])
    st.markdown("---")
    if st.button("清除快取"):
        st.cache_data.clear()
        st.rerun()

if module == "📊 股市情報站":
    render_dashboard()
elif module == "⚡ 當沖網格戰神":
    render_grid_bot()
