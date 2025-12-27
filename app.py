import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, time as dt_time
import pytz
import time
import feedparser
import requests

# ==========================================
# 1. 系統初始化 & CSS 風格
# ==========================================
st.set_page_config(page_title="股市特務 X", page_icon="🕵️", layout="wide")

st.markdown("""
    <style>
    /* 全局中文化 */
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', 'PingFang TC', sans-serif; }
    
    /* 導航條 */
    .nav-bar { 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px; color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .nav-title { font-size: 26px; font-weight: bold; letter-spacing: 1px; }
    
    /* 新聞列表優化 */
    .news-item { 
        padding: 15px; border-bottom: 1px solid #eee; background: white; 
        margin-bottom: 10px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        transition: 0.2s;
    }
    .news-item:hover { transform: translateY(-2px); border-left: 5px solid #1e3c72; }
    .news-link { 
        text-decoration: none; color: #2c3e50; font-weight: bold; font-size: 18px; 
        display: block; margin-bottom: 5px;
    }
    .news-link:hover { color: #ee3f2d; text-decoration: underline; }
    .news-meta { font-size: 13px; color: #888; }

    /* 機器人卡片 */
    .bot-card { border: 1px solid #ddd; border-radius: 10px; padding: 20px; margin-bottom: 15px; background: white; }
    .bot-active-border { border-left: 5px solid #4caf50; }
    .bot-inactive-border { border-left: 5px solid #9e9e9e; }
    
    .up { color: #d32f2f; } .down { color: #2e7d32; }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        self.watch_list = [
            "2330", "2317", "2454", "2603", "2609", "2615", "3231", "2382", "2356", "2303", 
            "2881", "2882", "2891", "2376", "2388", "3037", "3035", "3017", "2368", "3008",
            "1513", "1519", "1503", "1504", "2515", "2501", "2002", "1605", "2344", "2409"
        ]

    def is_market_open(self):
        now = datetime.now(self.tz)
        if now.weekday() >= 5: return False
        return dt_time(9, 0) <= now.time() <= dt_time(13, 30)

    @st.cache_data(ttl=60)
    def fetch_quote(_self, ticker):
        if not ticker.endswith('.TW') and not ticker.startswith('^'): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period='1d', interval='1m') # 嘗試抓取最新分鐘線以獲得最準確現價
            if df.empty:
                df = stock.history(period='5d', interval='1d') # 備用
            
            if df.empty: return None
            
            last = df.iloc[-1]
            price = float(last['Close']) # 確保轉為浮點數
            
            # 嘗試計算漲跌 (如果有前一筆)
            change = 0.0
            pct = 0.0
            if len(df) > 1:
                prev = df.iloc[-2]['Close']
                change = price - prev
                pct = (change / prev) * 100
                
            try: name = stock.info.get('longName', ticker)
            except: name = ticker
            
            return {
                "name": name, "price": price, "change": change,
                "pct": pct, "vol": last['Volume'], 
                "open": last['Open'], "high": last['High'], "low": last['Low']
            }
        except: return None

    @st.cache_data(ttl=300)
    def fetch_indices(_self):
        targets = {"加權指數": "^TWII", "櫃買指數": "^TWOII", "道瓊": "^DJI", "那斯達克": "^IXIC", "費半": "^SOX"}
        res = {}
        for name, sym in targets.items():
            q = _self.fetch_quote(sym)
            if q: res[name] = q
        return res

    @st.cache_data(ttl=60)
    def fetch_kline(_self, ticker):
        if not ticker.endswith('.TW'): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="3mo", interval="1d")
            df.reset_index(inplace=True)
            df['Date'] = df['Date'].dt.tz_localize(None)
            df.columns = [c.lower() for c in df.columns]
            return df
        except: return pd.DataFrame()

    @st.cache_data(ttl=300)
    def get_real_news(_self):
        # 改用 Google News RSS (台股關鍵字)，來源最廣且連結最穩定
        # Google News 會聚合 Yahoo, 經濟日報等來源
        rss_url = "https://news.google.com/rss/search?q=台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        
        news_items = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        try:
            response = requests.get(rss_url, headers=headers, timeout=5)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                if feed.entries:
                    for entry in feed.entries[:5]: # 取前5則
                        t = entry.published_parsed
                        time_str = f"{t.tm_hour:02}:{t.tm_min:02}" if t else "最新"
                        
                        news_items.append({
                            "title": entry.title,
                            "link": entry.link,
                            "time": time_str,
                            "source": entry.source.title if hasattr(entry, 'source') else "Google新聞"
                        })
        except: pass
            
        if not news_items:
            return [{"title": "目前無新聞或連線異常", "link": "#", "time": "--", "source": "系統"}]
        return news_items

    @st.cache_data(ttl=60)
    def scan_market(_self, min_p, max_p, strategy):
        data_list = []
        tickers_tw = [f"{x}.TW" for x in _self.watch_list]
        try:
            df = yf.download(tickers_tw, period="1d", group_by='ticker', threads=True, progress=False)
            for code in _self.watch_list:
                t_code = f"{code}.TW"
                if t_code not in df.columns.levels[0]: continue
                sub = df[t_code]
                if sub.empty: continue
                row = sub.iloc[-1]
                price = float(row['Close'])
                if not (min_p <= price <= max_p): continue
                open_p = float(row['Open'])
                change_pct = (price - open_p) / open_p * 100
                vol = int(row['Volume'])
                data_list.append({
                    "代號": code, "股價": price, "漲跌幅": change_pct, "成交量": vol,
                    "abs_change": abs(change_pct)
                })
            res = pd.DataFrame(data_list)
            if res.empty: return res
            if strategy == "漲跌停 (±10%)": return res.sort_values(by="abs_change", ascending=False).head(10)
            elif strategy == "爆量強勢股": return res.sort_values(by="成交量", ascending=False).head(10)
            elif strategy == "飆股 (漲幅排行)": return res.sort_values(by="漲跌幅", ascending=False).head(10)
            return res
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

# ==========================================
# 3. Session 狀態初始化 (修正初始化價格)
# ==========================================
if 'portfolio' not in st.session_state: st.session_state.portfolio = [{"code": "2330", "name": "台積電", "cost": 980, "qty": 1000}]
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'member_tier' not in st.session_state: st.session_state.member_tier = "一般會員"
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'line_uid' not in st.session_state: st.session_state.line_uid = ""

# 初始化機器人：啟動時直接抓台積電現價，不要用 1000.0
if 'bot_instances' not in st.session_state:
    default_code = "2330"
    init_q = engine.fetch_quote(default_code)
    init_price = float(init_q['price']) if init_q else 1000.0
    
    st.session_state.bot_instances = [
        # cur_price 是參考欄位，price 是觸發價
        {"id": i, "active": False, "code": default_code, "price": init_price, "qty": 1, "profit": 5.0, "loss": 2.0, "cur_price": init_price} 
        for i in range(5)
    ]

# 回調：當代號變更，更新現價並帶入觸發價
def on_bot_code_change(i):
    key = f"bc_{i}"
    code = st.session_state[key]
    q = engine.fetch_quote(code)
    if q:
        cur_p = float(q['price'])
        st.session_state.bot_instances[i]['cur_price'] = cur_p # 更新現價顯示
        st.session_state.bot_instances[i]['price'] = cur_p     # 觸發價預設為現價
        st.session_state.bot_instances[i]['code'] = code
        # 這裡不 toast 干擾畫面

def auto_fill_name():
    code = st.session_state.p_code_input
    if code:
        info = engine.fetch_quote(code)
        if info: st.session_state.p_name_input = info['name']

# 強制中文 K 線圖
def plot_chinese_chart(df, title, trigger_price=None):
    fig = go.Figure(data=[go.Candlestick(
        x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='日K',
        increasing_line_color='#d32f2f', decreasing_line_color='#2e7d32'
    )])
    fig.update_traces(hovertemplate='<b>日期</b>: %{x}<br><b>開盤</b>: %{open:.2f}<br><b>最高</b>: %{high:.2f}<br><b>最低</b>: %{low:.2f}<br><b>收盤</b>: %{close:.2f}<extra></extra>')
    if trigger_price:
        fig.add_hline(y=trigger_price, line_dash="dash", line_color="blue", annotation_text="觸發買進價")
    fig.update_layout(title=title, height=350, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="股價 (TWD)", hovermode="x unified")
    return fig

# ==========================================
# 4. 模組一：股市情報站 (Dashboard)
# ==========================================
def render_dashboard():
    st.markdown("<div class='nav-bar'><span class='nav-title'>🕵️ 股市情報站 (Intelligence Station)</span></div>", unsafe_allow_html=True)
    
    col_main, col_news = st.columns([3, 2])
    
    with col_main:
        st.subheader("📊 市場行情")
        indices = engine.fetch_indices()
        c_grid = st.columns(4)
        for i, (name, data) in enumerate(indices.items()):
            if i < 4:
                color = "up" if data['change'] > 0 else "down"
                with c_grid[i]:
                    st.markdown(f"""
                    <div class='card'>
                        <div class='card-title'>{name}</div>
                        <div class='card-val {color}'>{data['price']:,.0f}</div>
                        <div class='{color}'>{data['change']:+.0f} ({data['pct']:+.2f}%)</div>
                    </div>
                    """, unsafe_allow_html=True)
        st.divider()
        st.subheader("🔎 個股偵查 (K線圖)")
        ticker = st.text_input("輸入代號 (例如 2330)", "2330")
        df = engine.fetch_kline(ticker)
        if not df.empty:
            st.plotly_chart(plot_chinese_chart(df, f"{ticker} 技術走勢"), use_container_width=True, key="dash_chart")
        st.divider()
        st.subheader("🔥 市場熱點排行 (Scanner)")
        with st.container():
            st.info("💡 請設定兩大條件以開始搜尋")
            c_s1, c_s2, c_s3, c_s4 = st.columns([2, 2, 3, 2])
            min_p = c_s1.number_input("最低價 ($)", value=10, min_value=1)
            max_p = c_s2.number_input("最高價 ($)", value=1000, min_value=1)
            strat = c_s3.selectbox("篩選策略", ["漲跌停 (±10%)", "爆量強勢股", "飆股 (漲幅排行)"])
            if c_s4.button("🔍 開始掃描", type="primary", use_container_width=True):
                with st.spinner("正在掃描全市場數據..."):
                    res = engine.scan_market(min_p, max_p, strat)
                    if not res.empty:
                        st.success(f"搜尋完成！")
                        st.dataframe(res.style.format({"股價": "{:.2f}", "漲跌幅": "{:+.2f}%", "成交量": "{:,}"}), use_container_width=True)
                    else:
                        st.warning("查無符合條件股票")

    with col_news:
        st.subheader("📰 今日頭條 (Google News)")
        st.caption("點擊標題開啟新聞")
        with st.spinner("正在抓取最新新聞..."):
            news_list = engine.get_real_news()
        for news in news_list:
            st.markdown(f"""
            <div class='news-item'>
                <a href='{news['link']}' target='_blank' class='news-link'>{news['title']} 🔗</a>
                <div class='news-meta'>{news['time']} | {news['source']}</div>
            </div>
            """, unsafe_allow_html=True)
            
    st.divider()
    st.subheader("🎒 我的資產庫存")
    with st.expander("➕ 新增庫存紀錄", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        new_code = c1.text_input("代號", key="p_code_input", on_change=auto_fill_name)
        new_name = c2.text_input("名稱 (自動帶入)", key="p_name_input")
        new_cost = c3.number_input("平均成本", min_value=0.0)
        new_qty = c4.number_input("股數", min_value=1, step=1000)
        if st.button("加入"):
            if new_code:
                st.session_state.portfolio.append({"code": new_code, "name": new_name, "cost": new_cost, "qty": new_qty})
                st.rerun()
    if st.session_state.portfolio:
        p_data = []
        for item in st.session_state.portfolio:
            q = engine.fetch_quote(item['code'])
            curr = q['price'] if q else item['cost']
            prof = (curr - item['cost']) * item['qty']
            p_data.append({
                "代號": item['code'], "名稱": item['name'], "持有": item['qty'],
                "成本": item['cost'], "現價": f"{curr:.2f}", "損益": f"{prof:,.0f}"
            })
        st.dataframe(pd.DataFrame(p_data), use_container_width=True)

# ==========================================
# 5. 模組二：股市特務 X (Bot)
# ==========================================
def render_bot():
    st.markdown("<div class='nav-bar'><span class='nav-title'>🕵️ 股市特務 X (Auto-Trading Bot)</span></div>", unsafe_allow_html=True)
    
    if not st.session_state.login_status:
        st.warning("🔒 特務功能需驗證身分")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("憑證登入")
            st.selectbox("券商", ["元大", "凱基", "富邦", "永豐"])
            if st.button("🔐 模擬登入 (Demo)"):
                st.session_state.login_status = True
                st.rerun()
        return

    is_open = engine.is_market_open()
    status_msg = "🟢 市場開盤中 (系統運作正常)" if is_open else "🔴 休市中 (安全機制已啟動，無法下單)"
    if not is_open: st.error(f"⚠️ {status_msg}")
    else: st.success(status_msg)

    st.sidebar.divider()
    st.sidebar.header("🎫 會員權限")
    tier = st.sidebar.selectbox("切換等級", ["一般會員 (1筆)", "小資方案 (3筆)", "大佬方案 (5筆)"])
    limit = 1 if "一般" in tier else 3 if "小資" in tier else 5
    
    st.sidebar.divider()
    st.sidebar.header("🔔 LINE 通知 (Messaging API)")
    l_token = st.sidebar.text_input("Channel Token", value=st.session_state.line_token, type="password")
    l_uid = st.sidebar.text_input("User ID", value=st.session_state.line_uid)
    if st.sidebar.button("測試通知"):
        st.session_state.line_token = l_token
        st.session_state.line_uid = l_uid
        if engine.send_line_push(l_token, l_uid, "【股市特務X】連線測試成功！"):
            st.sidebar.success("發送成功")
        else: st.sidebar.error("失敗")

    st.info(f"權限：{tier} | 可執行：{limit} 筆")

    for i in range(limit):
        bot = st.session_state.bot_instances[i]
        active_css = "bot-active-border" if bot['active'] else "bot-inactive-border"
        status_txt = "🟢 監控中" if bot['active'] else "⚪ 待命"
        
        with st.expander(f"🤖 特務 #{i+1} [{bot['code']}] - {status_txt}", expanded=True):
            st.markdown(f"<div class='bot-card {active_css}'>", unsafe_allow_html=True)
            
            c_chart, c_ctrl = st.columns([2, 1])
            
            with c_chart:
                disabled = bot['active']
                
                # 修正後的 4 欄位
                c_1, c_2, c_3, c_4 = st.columns([1.5, 1.5, 1.5, 1.5])
                
                # 1. 代號 (觸發 on_change 更新現價)
                new_code = c_1.text_input(f"代號 #{i+1}", bot['code'], key=f"bc_{i}", disabled=disabled, on_change=on_bot_code_change, args=(i,))
                
                # 2. 現價 (唯讀，從 session state 讀取)
                cur_price_display = st.session_state.bot_instances[i]['cur_price']
                c_2.number_input(f"現價 (參考)", value=float(cur_price_display), disabled=True, key=f"bcp_{i}")
                
                # 3. 觸發價 (可編輯，輸入代號後會自動變成現價)
                new_price = c_3.number_input(f"觸發價 #{i+1}", value=float(st.session_state.bot_instances[i]['price']), key=f"bp_{i}", disabled=disabled)
                
                # 4. 張數
                new_qty = c_4.number_input(f"張數 #{i+1}", value=bot['qty'], key=f"bq_{i}", disabled=disabled)
                
                # 繪圖
                df_bot = engine.fetch_kline(new_code)
                if not df_bot.empty:
                    st.plotly_chart(plot_chinese_chart(df_bot, f"{new_code} 監控走勢", new_price), use_container_width=True, key=f"bot_chart_{i}")
                
                if not disabled:
                    st.session_state.bot_instances[i]['code'] = new_code
                    st.session_state.bot_instances[i]['price'] = new_price
                    st.session_state.bot_instances[i]['qty'] = new_qty

            with c_ctrl:
                st.write("#### 任務控制")
                st.info(f"監控目標: {new_code}\n條件: < {new_price} 元")
                
                if not bot['active']:
                    if st.button(f"🟢 啟動 #{i+1}", key=f"s_{i}", use_container_width=True, disabled=not is_open):
                        st.session_state.bot_instances[i]['active'] = True
                        msg = f"【啟動】\n標的: {new_code}\n條件: < {new_price}"
                        if st.session_state.line_token: engine.send_line_push(st.session_state.line_token, st.session_state.line_uid, msg)
                        st.rerun()
                else:
                    if st.button(f"🔴 停止 #{i+1}", key=f"e_{i}", use_container_width=True):
                        st.session_state.bot_instances[i]['active'] = False
                        msg = f"【停止】\n標的: {bot['code']}\n已手動停止"
                        if st.session_state.line_token: engine.send_line_push(st.session_state.line_token, st.session_state.line_uid, msg)
                        st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 6. 主程式導航
# ==========================================
with st.sidebar:
    st.title("🕵️ 股市特務 X")
    st.markdown("---")
    module = st.radio("導航", ["📊 股市情報站", "🤖 股市特務 X"])
    st.markdown("---")
    if st.button("清除快取"):
        st.cache_data.clear()
        st.rerun()

if module == "📊 股市情報站":
    render_dashboard()
elif module == "🤖 股市特務 X":
    render_bot()
