import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import requests
from datetime import datetime
import pytz

# ==========================================
# 1. 系統初始化 (這一行必須是全檔案的第一行程式碼)
# ==========================================
st.set_page_config(page_title="股市特務 X", page_icon="🔥", layout="wide")

# ★★★ 啟動檢查 (如果您看到這行字，代表程式沒壞) ★★★
status_placeholder = st.empty()
status_placeholder.info("🚀 系統核心啟動中，請稍候...")

# CSS 美化
st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', sans-serif; }
    .nav-bar { 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px; color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px; }
    .bot-card { border-left: 5px solid #4caf50; background: white; padding: 20px; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
    .up { color: #d32f2f; font-weight: bold; } 
    .down { color: #2e7d32; font-weight: bold; }
    .tag-sell { background: #ffebee; color: #c62828; padding: 2px 8px; border-radius: 4px; font-size:12px; font-weight:bold;}
    .tag-buy { background: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 4px; font-size:12px; font-weight:bold;}
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
        targets = ["^TWII", "^TWOII", "^DJI", "^SOX"]
        res = {}
        for sym in targets:
            q = _self.fetch_quote(sym)
            if q: res[sym] = q
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

    # 安全版新聞抓取 (避免卡死白屏)
    @st.cache_data(ttl=300)
    def get_news(_self):
        try:
            import feedparser
            feed = feedparser.parse("https://news.google.com/rss/search?q=台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant")
            return [{"title": e.title, "link": e.link, "time": "最新"} for e in feed.entries[:5]]
        except Exception as e:
            return [{"title": "新聞載入中或模組缺失", "link": "#", "time": "--"}]

    def fetch_stock_profile(self, ticker): 
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
if 'portfolio' not in st.session_state: st.session_state.portfolio = [{"code": "2330", "name": "台積電", "cost": 900.0, "qty": 1000}]
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'user_role' not in st.session_state: st.session_state.user_role = ""
if 'broker' not in st.session_state: st.session_state.broker = ""
if 'strategies' not in st.session_state: st.session_state.strategies = [] 
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
        <span style='color:white; float:right; margin-top:5px;'>👤 一般會員</span>
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
            if not df.empty: st.plotly_chart(plot_kline(df, f"{tk} {kt}"), use_container_width=True)
            
            # 基本面
            prof = engine.fetch_stock_profile(tk)
            if prof:
                c1, c2, c3 = st.columns(3)
                c1.metric("PE", prof['pe']); c2.metric("EPS", prof['eps']); c3.metric("殖利率", f"{prof['yield']:.2f}%")
            
            # 外部連結
            st.link_button("鉅亨網詳情", f"https://stock.cnyes.com/market/TWS:{tk}:STOCK")

        st.divider()
        
        # 掃描
        with st.expander("🔥 熱點掃描"):
            strat = st.selectbox("策略", ["漲幅排行 (飆股)", "爆量強勢股", "跌深反彈"])
            if st.button("掃描"):
                res = engine.scan_market(strat)
                st.dataframe(res, use_container_width=True)

    with c_side:
        # 新聞
        st.subheader("📰 市場快訊")
        news = engine.get_news()
        for n in news:
            st.markdown(f"<div class='news-item'><a class='news-link' href='{n['link']}' target='_blank'>{n['title']}</a><br><small>{n['time']}</small></div>", unsafe_allow_html=True)
        
        # 小金庫
        render_treasury()

# ==========================================
# 6. 模組 B：當沖網格戰神 (模擬登入+權限+LINE)
# ==========================================
TIER_MAP = {"一般會員": 1, "小資會員": 3, "大佬會員": 5}

def render_grid_bot():
    # 1. 登入畫面 (Gatekeeper)
    if not st.session_state.login_status:
        st.markdown("<div class='nav-bar'><span class='nav-title'>⚡ 網格戰神 (鎖定中)</span></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.subheader("🔒 模擬登入系統")
            with st.form("login_form"):
                bk = st.selectbox("券商", ["元大證券", "凱基證券", "富邦證券"])
                # 會員分級選擇
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

    # 2. 登入後畫面
    limit = TIER_MAP[st.session_state.user_role]
    used = len(st.session_state.strategies)
    
    st.markdown(f"""
    <div class='nav-bar'>
        <span class='nav-title'>⚡ 當沖網格戰神</span>
        <span style='float:right; margin-top:5px; color:white;'>
            👤 {st.session_state.user_role} (額度: {used}/{limit}) | {st.session_state.broker}
        </span>
    </div>""", unsafe_allow_html=True)

    # LINE Token 設定
    with st.expander("📢 LINE 通知設定", expanded=False):
        c1, c2 = st.columns(2)
        st.session_state.line_token = c1.text_input("Token", st.session_state.line_token, type="password")
        st.session_state.line_uid = c2.text_input("User ID", st.session_state.line_uid)

    # 新增策略
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
                st.subheader(f"{s['code']} (現價: {curr})")
                st.caption(f"區間: {s['lower']}~{s['upper']} | 格數: {s['grids']}")
                c1, c2 = st.columns(2)
                if near_s: c1.markdown(f"<span class='tag-sell'>🔴 賣壓: {near_s:.2f}</span>", unsafe_allow_html=True)
                if near_b: c2.markdown(f"<span class='tag-buy'>🟢 支撐: {near_b:.2f}</span>", unsafe_allow_html=True)

            with c_act:
                if st.button("🗑️ 刪除", key=f"del_{i}"):
                    st.session_state.strategies.pop(i)
                    st.rerun()
                
                # LINE 按鈕
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
# 6. 主程式導航
# ==========================================
status_placeholder.empty() # 清除載入訊息

with st.sidebar:
    st.title("🕵️ 股市特務 X")
    st.markdown("---")
    
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

