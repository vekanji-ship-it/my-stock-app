import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime
import pytz
import requests

# 嘗試匯入 feedparser，如果沒有就跳過，避免白屏
try:
    import feedparser
except ImportError:
    feedparser = None

# ==========================================
# 1. 系統初始化 (必須第一行)
# ==========================================
st.set_page_config(page_title="股市特務 X", page_icon="🔥", layout="wide")

# CSS 風格設定 (保留原版藍色風格)
st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', sans-serif; }
    .nav-bar { 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px; color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px; }
    
    /* 網格戰神專用卡片 */
    .grid-card { border-left: 5px solid #ff9800; background: white; padding: 20px; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
    
    .up { color: #d32f2f; font-weight: bold; } 
    .down { color: #2e7d32; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎 (DataEngine)
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        self.watch_list = ["2330", "2317", "2454", "2603", "0050", "00632R"]

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
            return {"name": ticker, "price": price, "change": change, "pct": pct, "vol": df.iloc[-1].get('Volume', 0)}
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

    @st.cache_data(ttl=60)
    def scan_market(_self, strategy):
        # 模擬掃描邏輯 (保留您要的功能)
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
        if not feedparser: return []
        try:
            feed = feedparser.parse("https://news.google.com/rss/search?q=台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant")
            return [{"title": e.title, "link": e.link, "time": "最新"} for e in feed.entries[:5]]
        except: return []

engine = DataEngine()

# 繪圖函數
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
# 3. Session 狀態管理
# ==========================================
if 'portfolio' not in st.session_state: st.session_state.portfolio = [{"code": "2330", "name": "台積電", "cost": 900.0, "qty": 1000}]
# 網格機器人專用狀態
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'user_role' not in st.session_state: st.session_state.user_role = ""
if 'broker' not in st.session_state: st.session_state.broker = ""
if 'strategies' not in st.session_state: st.session_state.strategies = [] 
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'line_uid' not in st.session_state: st.session_state.line_uid = ""

# ==========================================
# 4. 模組一：股市情報站 (Dashboard) - 原版保留
# ==========================================
def render_dashboard():
    st.markdown("<div class='nav-bar'><span class='nav-title'>🕵️ 股市情報站</span></div>", unsafe_allow_html=True)
    col_main, col_news = st.columns([3, 2])
    
    with col_main:
        st.subheader("🔎 全方位個股偵查")
        tk = st.text_input("輸入代號", "2330")
        q = engine.fetch_quote(tk)
        
        if q:
            c = "up" if q['change']>0 else "down"
            st.markdown(f"<div class='card'><h2>{q['name']} {q['price']} <span class='{c}'>{q['change']:+.2f} ({q['pct']:+.2f}%)</span></h2></div>", unsafe_allow_html=True)
            
            # K線圖
            kt = st.radio("週期", ["日K", "週K", "月K"], horizontal=True)
            kp, ki = ("3mo","1d") if kt=="日K" else ("1y","1wk") if kt=="週K" else ("5y","1mo")
            df = engine.fetch_kline(tk, kp, ki)
            if not df.empty: st.plotly_chart(plot_kline(df, f"{tk} {kt}"), use_container_width=True)
        
        st.divider()
        # 掃描
        with st.expander("🔥 熱點掃描"):
            strat = st.selectbox("策略", ["漲幅排行 (飆股)", "爆量強勢股", "跌深反彈"])
            if st.button("開始掃描"):
                res = engine.scan_market(strat)
                st.dataframe(res, use_container_width=True)

    with col_news:
        st.subheader("📰 新聞")
        news = engine.get_news()
        for n in news:
            st.markdown(f"<div style='border-bottom:1px solid #eee; padding:5px'><a href='{n['link']}'>{n['title']}</a></div>", unsafe_allow_html=True)
        
        st.divider()
        # 小金庫 (保留新增刪除功能)
        st.subheader("🎒 小金庫")
        if st.session_state.portfolio:
            p_data = []
            for i in st.session_state.portfolio:
                curr = engine.fetch_quote(i['code'])['price'] or i['cost']
                prof = (curr - i['cost']) * i['qty']
                p_data.append({"代號": i['code'], "成本": i['cost'], "現價": curr, "損益": prof})
            st.dataframe(pd.DataFrame(p_data), use_container_width=True)

        t1, t2 = st.tabs(["➕ 新增", "🗑️ 刪除"])
        with t1:
            pc = st.text_input("代號", key="pc")
            pco = st.number_input("成本", key="pco")
            pq = st.number_input("股數", 1000, key="pq")
            if st.button("加入"):
                st.session_state.portfolio.append({"code":pc, "name":pc, "cost":pco, "qty":pq})
                st.rerun()
        with t2:
            if st.session_state.portfolio:
                opts = [f"{x['code']}" for x in st.session_state.portfolio]
                sels = st.multiselect("刪除", opts)
                if st.button("確認刪除") and sels:
                    st.session_state.portfolio = [x for x in st.session_state.portfolio if x['code'] not in sels]
                    st.rerun()

# ==========================================
# 5. 模組二：當沖網格戰神 (Grid Bot) - 全新功能植入
# ==========================================
TIER_MAP = {"一般會員": 1, "小資會員": 3, "大佬會員": 5}

def render_grid_bot():
    # === 1. 登入檢查 (若未登入，顯示登入畫面) ===
    if not st.session_state.login_status:
        st.markdown("<div class='nav-bar'><span class='nav-title'>⚡ 網格戰神 (請登入)</span></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("<div class='card' style='text-align:center;'>", unsafe_allow_html=True)
            st.subheader("🔒 模擬登入系統")
            
            with st.form("login_form"):
                bk = st.selectbox("券商", ["元大", "凱基", "富邦"])
                # 您的要求：會員分級
                role = st.selectbox("會員等級", ["一般會員", "小資會員", "大佬會員"])
                acc = st.text_input("帳號 (任意)")
                pwd = st.text_input("密碼 (任意)", type="password")
                
                if st.form_submit_button("🚀 登入"):
                    if pwd:
                        st.session_state.login_status = True
                        st.session_state.user_role = role
                        st.session_state.broker = bk
                        st.rerun()
                    else: st.error("請輸入密碼")
            st.markdown("</div>", unsafe_allow_html=True)
        return

    # === 2. 登入後：操盤介面 ===
    limit = TIER_MAP[st.session_state.user_role]
    used = len(st.session_state.strategies)
    
    st.markdown(f"""
    <div class='nav-bar'>
        <span class='nav-title'>⚡ 當沖網格戰神 | {st.session_state.broker}</span>
        <span style='float:right; margin-top:5px; color:white;'>
            👤 {st.session_state.user_role} (額度: {used}/{limit})
        </span>
    </div>""", unsafe_allow_html=True)

    # LINE Token 設定
    with st.expander("📢 LINE 通知設定", expanded=False):
        c1, c2 = st.columns(2)
        st.session_state.line_token = c1.text_input("Token", st.session_state.line_token, type="password")
        st.session_state.line_uid = c2.text_input("User ID", st.session_state.line_uid)

    # 新增策略 (受等級限制)
    if used < limit:
        with st.expander("➕ 新增網格監控", expanded=True):
            with st.form("add_grid"):
                c1, c2, c3, c4, c5 = st.columns(5)
                code = c1.text_input("代號", "00632R")
                upper = c2.number_input("上限", 100.0)
                lower = c3.number_input("下限", 80.0)
                grids = c4.number_input("格數", 10, min_value=2)
                disc = c5.number_input("手續費折數", 0.6)
                if st.form_submit_button("💾 加入"):
                    st.session_state.strategies.append({"code": code, "upper": upper, "lower": lower, "grids": grids, "disc": disc})
                    st.rerun()
    else:
        st.warning(f"⚠️ 您的 {st.session_state.user_role} 額度 ({limit}筆) 已滿。")

    # 監控列表
    st.markdown("### 📋 監控中列表")
    if not st.session_state.strategies: st.info("目前無監控策略")

    for i, s in enumerate(st.session_state.strategies):
        with st.container():
            st.markdown("<div class='grid-card'>", unsafe_allow_html=True)
            c_info, c_act = st.columns([3, 1])
            
            # 計算
            q = engine.fetch_quote(s['code'])
            curr = q['price'] if q else 0
            step = (s['upper'] - s['lower']) / s['grids']
            levels = [s['lower'] + x * step for x in range(s['grids'] + 1)]
            near_s = min([p for p in levels if p > curr], default=None)
            near_b = max([p for p in levels if p < curr], default=None)

            with c_info:
                st.subheader(f"{s['code']} (現價: {curr})")
                st.caption(f"區間: {s['lower']}~{s['upper']} | 格數: {s['grids']}")
                c1, c2 = st.columns(2)
                if near_s: c1.error(f"賣壓: {near_s:.2f}")
                if near_b: c2.success(f"支撐: {near_b:.2f}")

            with c_act:
                if st.button("🗑️ 刪除", key=f"del_{i}"):
                    st.session_state.strategies.pop(i)
                    st.rerun()
                
                # LINE 通知按鈕 (含費用試算)
                if st.button("📤 Line 通知", key=f"ln_{i}"):
                    if st.session_state.line_token:
                        fb, _, _ = calc_fee(near_b or 0, 1, "BUY", s['disc'])
                        fs, _, _ = calc_fee(near_s or 0, 1, "SELL", s['disc'])
                        msg = f"【網格快報】\n{s['code']} 現價:{curr}\n買點:{near_b}(含費${fb})\n賣點:{near_s}(含費稅${fs})"
                        if engine.send_line_push(st.session_state.line_token, st.session_state.line_uid, msg):
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
    
    # 登出按鈕 (讓您可以重測登入)
    if st.session_state.login_status:
        st.success(f"已登入: {st.session_state.user_role}")
        if st.button("登出 (切換帳號)"):
            st.session_state.login_status = False
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
