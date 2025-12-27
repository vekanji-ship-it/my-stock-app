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
# 1. 系統初始化 & CSS (保留原版漂亮風格)
# ==========================================
st.set_page_config(page_title="股市特務 X", page_icon="🕵️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', sans-serif; }
    .nav-bar { 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px; color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .nav-title { font-size: 26px; font-weight: bold; letter-spacing: 1px; }
    .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px; }
    .bot-card { border: 1px solid #ddd; border-radius: 10px; padding: 20px; margin-bottom: 15px; background: white; border-left: 5px solid #4caf50; }
    .up { color: #d32f2f; font-weight: bold; } 
    .down { color: #2e7d32; font-weight: bold; }
    .news-item { padding: 10px; border-bottom: 1px solid #eee; }
    .news-link { text-decoration: none; color: #333; font-weight: bold; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎 (完整保留)
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        self.name_map = {
            "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2603": "長榮", "0050": "元大台灣50",
            "0056": "元大高股息", "00878": "國泰永續高股息", "00632R": "元大台灣50反1",
            "^TWII": "加權指數", "^TWOII": "櫃買指數", "^DJI": "道瓊", "^SOX": "費半"
        }
        # 模擬掃描清單
        self.watch_list = ["2330", "2317", "2454", "2603", "2609", "2615", "3231", "2382", "2356", "2303", "1513", "1519"]

    def get_stock_name(self, ticker):
        clean = ticker.replace('.TW', '')
        return self.name_map.get(clean, ticker)

    @st.cache_data(ttl=10)
    def fetch_quote(_self, ticker):
        if not ticker.endswith('.TW') and not ticker.startswith('^') and ticker.isdigit(): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period='1d', interval='1m')
            if df.empty: df = stock.history(period='5d', interval='1d')
            if df.empty: return None
            price = float(df.iloc[-1]['Close'])
            change = price - df.iloc[-2]['Close'] if len(df) > 1 else 0
            pct = (change / df.iloc[-2]['Close']) * 100 if len(df) > 1 else 0
            return {
                "name": _self.get_stock_name(ticker.replace('.TW', '')),
                "price": price, "change": change, "pct": pct, "vol": df.iloc[-1].get('Volume', 0),
                "open": df.iloc[-1]['Open'], "high": df.iloc[-1]['High'], "low": df.iloc[-1]['Low']
            }
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

    @st.cache_data(ttl=300)
    def fetch_indices(_self):
        targets = ["^TWII", "^TWOII", "^DJI", "^SOX"]
        res = {}
        for sym in targets:
            q = _self.fetch_quote(sym)
            if q: res[q['name']] = q
        return res

    @st.cache_data(ttl=300)
    def fetch_stock_profile(_self, ticker):
        if not ticker.endswith('.TW') and ticker.isdigit(): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return {"pe": info.get('trailingPE'), "eps": info.get('trailingEps'), "yield": info.get('dividendYield', 0)*100}
        except: return None

    @st.cache_data(ttl=300)
    def get_real_news(_self):
        try:
            feed = feedparser.parse("https://news.google.com/rss/search?q=台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant")
            return [{"title": e.title, "link": e.link, "time": f"{e.published_parsed.tm_hour:02}:{e.published_parsed.tm_min:02}"} for e in feed.entries[:5]]
        except: return []

    @st.cache_data(ttl=60)
    def scan_market(_self, strategy):
        data_list = []
        for code in _self.watch_list:
            q = _self.fetch_quote(code)
            if q:
                data_list.append({
                    "代號": code, "名稱": q['name'], "股價": q['price'], 
                    "漲跌幅": q['pct'], "成交量": q['vol'], "abs_change": abs(q['pct'])
                })
        res = pd.DataFrame(data_list)
        if res.empty: return res
        
        if strategy == "漲幅排行 (飆股)": return res.sort_values(by="漲跌幅", ascending=False)
        elif strategy == "爆量強勢股": return res.sort_values(by="成交量", ascending=False)
        elif strategy == "跌深反彈": return res.sort_values(by="漲跌幅", ascending=True)
        return res

    def send_line_push(self, token, user_id, message):
        try:
            r = requests.post("https://api.line.me/v2/bot/message/push", 
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                json={"to": user_id, "messages": [{"type": "text", "text": message}]})
            return r.status_code == 200
        except: return False

engine = DataEngine()

# 繪圖函數
def plot_chart(df, title, levels=None):
    x_col = 'datetime' if 'datetime' in df.columns else 'date'
    fig = go.Figure(data=[go.Candlestick(x=df[x_col], open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#d32f2f', decreasing_line_color='#2e7d32')])
    if levels:
        for p in levels: fig.add_hline(y=p, line_dash="dot", line_color="gray", line_width=1)
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
if 'portfolio' not in st.session_state: st.session_state.portfolio = [{"code": "2330", "name": "台積電", "cost": 980, "qty": 1000}]
# 網格戰神專用狀態
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'member_tier' not in st.session_state: st.session_state.member_tier = "一般會員"
if 'grid_strategies' not in st.session_state: st.session_state.grid_strategies = []
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'line_uid' not in st.session_state: st.session_state.line_uid = ""

# ==========================================
# 4. 模組一：股市情報站 (保留完整功能)
# ==========================================
def render_dashboard():
    st.markdown("<div class='nav-bar'><span class='nav-title'>🕵️ 股市情報站</span></div>", unsafe_allow_html=True)
    col_main, col_news = st.columns([3, 2])
    
    with col_main:
        # A. 大盤
        st.subheader("📊 市場行情")
        indices = engine.fetch_indices()
        c_grid = st.columns(4)
        idx = 0
        for name, data in indices.items():
            if idx < 4:
                color = "up" if data['change'] > 0 else "down"
                c_grid[idx].metric(name, f"{data['price']:,.0f}", f"{data['pct']:.2f}%")
                idx += 1
        st.divider()
        
        # B. 個股偵查
        st.subheader("🔎 全方位個股偵查")
        ticker = st.text_input("輸入代號", "2330")
        q = engine.fetch_quote(ticker)
        prof = engine.fetch_stock_profile(ticker)
        
        if q:
            c = "up" if q['change']>0 else "down"
            st.markdown(f"<div class='card'><h2>{q['name']} {q['price']} <span class='{c}'>{q['change']:+.2f} ({q['pct']:+.2f}%)</span></h2></div>", unsafe_allow_html=True)
            
            tab1, tab2, tab3 = st.tabs(["📈 技術走勢", "📋 基本資料", "🔗 外部連結"])
            with tab1:
                k_type = st.radio("週期", ["日K", "週K", "月K"], horizontal=True)
                kp, ki = ("3mo","1d") if k_type=="日K" else ("1y","1wk") if k_type=="週K" else ("5y","1mo")
                df_k = engine.fetch_kline(ticker, kp, ki)
                if not df_k.empty: st.plotly_chart(plot_chart(df_k, f"{q['name']} {k_type}"), use_container_width=True)
            with tab2:
                if prof:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("PE", prof['pe']); c2.metric("EPS", prof['eps']); c3.metric("殖利率", f"{prof['yield']:.2f}%")
            with tab3:
                st.link_button("鉅亨網詳情", f"https://stock.cnyes.com/market/TWS:{ticker}:STOCK")
        
        st.divider()
        # C. 掃描
        with st.expander("🔥 市場熱點掃描"):
            strat = st.selectbox("策略", ["漲幅排行 (飆股)", "爆量強勢股", "跌深反彈"])
            if st.button("開始掃描"):
                res = engine.scan_market(strat)
                st.dataframe(res, use_container_width=True)

    with col_news:
        # D. 新聞
        st.subheader("📰 今日頭條")
        news = engine.get_real_news()
        for n in news:
            st.markdown(f"<div class='news-item'><a class='news-link' href='{n['link']}' target='_blank'>{n['title']}</a><br><small>{n['time']}</small></div>", unsafe_allow_html=True)
        
        st.divider()
        # E. 台股小金庫 (含刪除功能)
        st.subheader("🎒 台股小金庫")
        if st.session_state.portfolio:
            p_data = []
            tp = 0
            for i in st.session_state.portfolio:
                pq = engine.fetch_quote(i['code'])
                curr = pq['price'] if pq else i['cost']
                prof = (curr - i['cost']) * i['qty']
                tp += prof
                p_data.append({"名稱": i['name'], "現價": curr, "損益": prof})
            st.metric("總損益", f"${tp:,.0f}")
            st.dataframe(pd.DataFrame(p_data), use_container_width=True)
        else: st.info("無庫存")

        t1, t2 = st.tabs(["➕ 新增", "🗑️ 刪除"])
        with t1:
            c1, c2 = st.columns(2)
            pc = c1.text_input("代號", key="pc")
            pn = c2.text_input("名稱", key="pn")
            pco = c1.number_input("成本", key="pco")
            pq = c2.number_input("股數", 1000, key="pq")
            if st.button("加入"):
                st.session_state.portfolio.append({"code":pc, "name":pn or pc, "cost":pco, "qty":pq})
                st.rerun()
        with t2:
            if st.session_state.portfolio:
                opts = [f"{x['code']} {x['name']}" for x in st.session_state.portfolio]
                sels = st.multiselect("刪除", opts)
                if st.button("確認刪除") and sels:
                    st.session_state.portfolio = [x for x in st.session_state.portfolio if f"{x['code']} {x['name']}" not in sels]
                    st.rerun()

# ==========================================
# 5. 模組二：當沖網格戰神 (全新替換版)
# ==========================================
def render_grid_bot():
    TIER_LIMITS = {"一般會員": 1, "小資會員": 3, "大佬會員": 5}

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
                        st.session_state.member_tier = role
                        st.rerun()
                    else: st.error("請輸入密碼")
            st.markdown("</div>", unsafe_allow_html=True)
        return

    # 2. 登入後畫面
    limit = TIER_LIMITS[st.session_state.member_tier]
    used = len(st.session_state.grid_strategies)
    
    st.markdown(f"""
    <div class='nav-bar'>
        <span class='nav-title'>⚡ 當沖網格戰神</span>
        <span style='float:right; margin-top:5px; background:rgba(255,255,255,0.2); padding:5px 10px; border-radius:15px;'>
            👤 {st.session_state.member_tier} (額度: {used}/{limit})
        </span>
    </div>""", unsafe_allow_html=True)

    # LINE Token 設定
    with st.expander("📢 LINE 通知設定", expanded=False):
        c1, c2 = st.columns(2)
        st.session_state.line_token = c1.text_input("Token", st.session_state.line_token, type="password")
        st.session_state.line_uid = c2.text_input("User ID", st.session_state.line_uid)

    # 新增策略
    if used < limit:
        with st.expander("➕ 新增監控策略", expanded=True):
            with st.form("add_grid"):
                c1, c2, c3, c4, c5 = st.columns(5)
                code = c1.text_input("代號", "00632R")
                upper = c2.number_input("上限", 100.0)
                lower = c3.number_input("下限", 80.0)
                grids = c4.number_input("格數", 10, min_value=2)
                disc = c5.number_input("手續費折數", 0.6)
                if st.form_submit_button("💾 加入"):
                    st.session_state.grid_strategies.append({"code": code, "upper": upper, "lower": lower, "grids": grids, "disc": disc})
                    st.rerun()
    else:
        st.warning(f"⚠️ 您的 {st.session_state.member_tier} 額度 ({limit}筆) 已滿。")

    # 監控列表
    st.markdown("### 📋 監控中列表")
    if not st.session_state.grid_strategies: st.info("目前無監控策略")

    for i, s in enumerate(st.session_state.grid_strategies):
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
                if near_s: c1.error(f"賣壓: {near_s:.2f}")
                if near_b: c2.success(f"支撐: {near_b:.2f}")

            with c_act:
                if st.button("🗑️ 刪除", key=f"del_{i}"):
                    st.session_state.grid_strategies.pop(i)
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
with st.sidebar:
    st.title("🕵️ 股市特務 X")
    st.markdown("---")
    
    if st.session_state.login_status:
        st.success(f"已登入: {st.session_state.member_tier}")
        if st.button("登出 (切換帳號)"):
            st.session_state.login_status = False
            st.session_state.grid_strategies = []
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
