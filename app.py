import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, time as dt_time
import pytz
import time
import feedparser
import requests # 用於發送 LINE 通知

# ==========================================
# 1. 系統初始化 & CSS 風格 (特務風格)
# ==========================================
st.set_page_config(page_title="股市特務 X", page_icon="🕵️", layout="wide")

st.markdown("""
    <style>
    /* 全局設定 */
    .stApp { background-color: #f0f2f6; font-family: 'Microsoft JhengHei', sans-serif; }
    
    /* 頂部導航條 */
    .nav-bar { 
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); 
        padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px; color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .nav-title { font-size: 26px; font-weight: bold; letter-spacing: 1px; }
    
    /* 卡片優化 */
    .card { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); text-align: center; }
    .card-title { font-size: 14px; color: #666; }
    .card-val { font-size: 22px; font-weight: bold; }
    
    /* 漲跌色 */
    .up { color: #d32f2f; } .down { color: #2e7d32; } .flat { color: #555; }
    
    /* 新聞列表 */
    .news-item { padding: 12px; border-bottom: 1px solid #eee; background: white; margin-bottom: 8px; border-radius: 8px; transition: 0.2s; }
    .news-item:hover { transform: translateX(5px); border-left: 4px solid #1e3c72; }
    .news-link { text-decoration: none; color: #333; font-weight: bold; font-size: 16px; display: block; }
    .news-link:hover { color: #1e3c72; }
    .news-meta { font-size: 12px; color: #888; margin-top: 5px; }

    /* 機器人狀態燈 */
    .bot-active { border-left: 5px solid #4caf50; background-color: #e8f5e9; padding: 10px; border-radius: 5px; }
    .bot-inactive { border-left: 5px solid #9e9e9e; background-color: #f5f5f5; padding: 10px; border-radius: 5px; }

    /* 隱藏預設元件 */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        # 內建熱門股清單
        self.watch_list = ["2330", "2317", "2454", "2603", "2609", "2615", "3231", "2382", "2356", "2303"]

    def get_market_status(self):
        now = datetime.now(self.tz)
        if now.weekday() >= 5: return "CLOSED"
        if dt_time(9, 0) <= now.time() <= dt_time(13, 30): return "OPEN"
        return "CLOSED"

    @st.cache_data(ttl=60)
    def fetch_quote(_self, ticker):
        if not ticker.endswith('.TW') and not ticker.startswith('^'): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period='5d', interval='1d')
            if df.empty: return None
            last = df.iloc[-1]
            prev = df.iloc[-2]
            try: name = stock.info.get('longName', ticker)
            except: name = ticker
            return {
                "name": name, "price": last['Close'], "change": last['Close'] - prev['Close'],
                "pct": (last['Close'] - prev['Close']) / prev['Close'] * 100,
                "vol": last['Volume'], "open": last['Open'], "high": last['High'], "low": last['Low']
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
        # 增強版新聞抓取，避免空白
        rss_urls = [
            "https://news.cnyes.com/rss/cat/twstock", # 鉅亨台股
            "https://news.cnyes.com/rss/cat/headline" # 鉅亨頭條
        ]
        news_items = []
        for url in rss_urls:
            try:
                feed = feedparser.parse(url)
                if not feed.entries: continue
                for entry in feed.entries[:5]: # 每個源抓5則
                    if any(x['link'] == entry.link for x in news_items): continue # 去重
                    t = entry.published_parsed
                    time_str = f"{t.tm_hour:02}:{t.tm_min:02}" if t else "最新"
                    news_items.append({"title": entry.title, "link": entry.link, "time": time_str, "source": "鉅亨網"})
                if len(news_items) >= 8: break
            except: pass
            
        if not news_items:
            return [{"title": "目前無最新新聞 (連線重試中)", "link": "#", "time": "--", "source": "系統"}]
        return news_items

    def send_line_notify(self, token, message):
        """發送 LINE Notify"""
        url = "https://notify-api.line.me/api/notify"
        headers = {"Authorization": "Bearer " + token}
        payload = {'message': message}
        try:
            r = requests.post(url, headers=headers, params=payload)
            return r.status_code == 200
        except:
            return False

engine = DataEngine()

# ==========================================
# 3. Session 狀態管理 (含機器人多筆邏輯)
# ==========================================
if 'portfolio' not in st.session_state: 
    st.session_state.portfolio = [{"code": "2330", "name": "台積電", "cost": 980, "qty": 1000}]
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'member_tier' not in st.session_state: st.session_state.member_tier = "一般會員" # 預設
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'bot_instances' not in st.session_state:
    # 初始化 5 個機器人插槽
    st.session_state.bot_instances = [
        {"id": i, "active": False, "code": "2330", "price": 1000.0, "qty": 1, "profit": 5.0, "loss": 2.0} 
        for i in range(5)
    ]

# Helper: 自動填入名稱
def auto_fill_name():
    code = st.session_state.p_code_input
    if code:
        info = engine.fetch_quote(code)
        if info: st.session_state.p_name_input = info['name']

# ==========================================
# 4. 模組一：股市情報站 (原戰情室)
# ==========================================
def render_dashboard():
    st.markdown("<div class='nav-bar'><span class='nav-title'>🕵️ 股市情報站 (Intelligence Station)</span></div>", unsafe_allow_html=True)
    
    col_idx, col_news = st.columns([3, 2])
    
    with col_idx:
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
        st.subheader("🔎 個股偵查")
        ticker = st.text_input("輸入代號 (例如 2330)", "2330")
        df = engine.fetch_kline(ticker)
        
        if not df.empty:
            fig = go.Figure(data=[go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
            fig.update_layout(height=400, xaxis_rangeslider_visible=False, title=f"{ticker} 技術線圖", margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig, use_container_width=True)
    
    with col_news:
        st.subheader("📰 今日頭條 (Anue)")
        with st.spinner("正在解密新聞數據..."):
            news_list = engine.get_real_news()
            
        for news in news_list:
            st.markdown(f"""
            <div class='news-item'>
                <a href='{news['link']}' target='_blank' class='news-link'>{news['title']}</a>
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
                st.success(f"已新增 {new_name}")
                time.sleep(0.5)
                st.rerun()

    if st.session_state.portfolio:
        p_data = []
        tot_p = 0; tot_a = 0
        for item in st.session_state.portfolio:
            q = engine.fetch_quote(item['code'])
            curr = q['price'] if q else item['cost']
            val = curr * item['qty']
            cost = item['cost'] * item['qty']
            prof = val - cost
            pct = (prof / cost * 100) if cost > 0 else 0
            tot_a += val; tot_p += prof
            p_data.append({
                "代號": item['code'], "名稱": item['name'], "持有": item['qty'],
                "成本": item['cost'], "現價": f"{curr:.2f}", "損益": f"{prof:,.0f}", "報酬率": f"{pct:+.2f}%"
            })
        st.dataframe(pd.DataFrame(p_data), use_container_width=True)

# ==========================================
# 5. 模組二：股市特務 X (交易機器人)
# ==========================================
def render_bot():
    st.markdown("<div class='nav-bar'><span class='nav-title'>🕵️ 股市特務 X (Auto-Trading Bot)</span></div>", unsafe_allow_html=True)
    
    # 登入檢查
    if not st.session_state.login_status:
        st.warning("🔒 特務功能需驗證身分")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("憑證登入")
            broker = st.selectbox("券商", ["元大", "凱基", "富邦", "永豐"])
            if st.button("🔐 模擬登入 (Demo)"):
                st.session_state.login_status = True
                st.success("身分驗證成功")
                st.rerun()
        return

    # 會員權限管理
    st.sidebar.divider()
    st.sidebar.header("🎫 會員權限設定 (模擬)")
    # 模擬切換會員等級
    tier = st.sidebar.selectbox("切換會員等級", ["一般會員 (1筆)", "小資方案 (3筆)", "大佬方案 (5筆)"])
    if "一般" in tier: limit = 1
    elif "小資" in tier: limit = 3
    else: limit = 5
    st.session_state.member_tier = tier

    # LINE Token 設定
    st.sidebar.divider()
    st.sidebar.header("🔔 LINE 通知設定")
    line_t = st.sidebar.text_input("輸入 LINE Notify Token", value=st.session_state.line_token, type="password")
    st.session_state.line_token = line_t
    if st.sidebar.button("測試 LINE 通知"):
        if engine.send_line_notify(line_t, "\n【股市特務X】系統連線測試成功！"):
            st.sidebar.success("發送成功！")
        else:
            st.sidebar.error("發送失敗，請檢查 Token")

    # 主畫面
    st.info(f"👋 歡迎回來，特務。目前權限：**{tier}** (可執行 {limit} 筆任務)")

    # 迴圈渲染機器人插槽
    for i in range(limit):
        bot = st.session_state.bot_instances[i]
        
        # 樣式容器
        status_color = "🟢 監控中" if bot['active'] else "⚪ 待命"
        container_css = "bot-active" if bot['active'] else "bot-inactive"
        
        with st.expander(f"🤖 特務機器人 #{i+1} - [{status_color}] {bot['code']}", expanded=True):
            
            c_set, c_act = st.columns([3, 1])
            
            with c_set:
                # 參數設定區 (如果是啟動狀態，則鎖定輸入框)
                disabled = bot['active']
                c1, c2, c3 = st.columns(3)
                new_code = c1.text_input(f"監控代號 #{i+1}", bot['code'], key=f"b_code_{i}", disabled=disabled)
                new_price = c2.number_input(f"觸發價 #{i+1}", value=bot['price'], key=f"b_price_{i}", disabled=disabled)
                new_qty = c3.number_input(f"張數 #{i+1}", value=bot['qty'], key=f"b_qty_{i}", disabled=disabled)
                
                c4, c5 = st.columns(2)
                new_profit = c4.number_input(f"停利 % #{i+1}", value=bot['profit'], key=f"b_prof_{i}", disabled=disabled)
                new_loss = c5.number_input(f"停損 % #{i+1}", value=bot['loss'], key=f"b_loss_{i}", disabled=disabled)
                
                # 更新 state (未啟動時)
                if not disabled:
                    st.session_state.bot_instances[i]['code'] = new_code
                    st.session_state.bot_instances[i]['price'] = new_price
                    st.session_state.bot_instances[i]['qty'] = new_qty
                    st.session_state.bot_instances[i]['profit'] = new_profit
                    st.session_state.bot_instances[i]['loss'] = new_loss

            with c_act:
                st.write("#### 任務控制")
                if not bot['active']:
                    if st.button(f"🟢 開始執行 #{i+1}", key=f"start_{i}", use_container_width=True):
                        st.session_state.bot_instances[i]['active'] = True
                        msg = f"\n【任務啟動】\n代號: {new_code}\n觸發價: {new_price}\n數量: {new_qty}張"
                        if st.session_state.line_token:
                            engine.send_line_notify(st.session_state.line_token, msg)
                        st.rerun()
                else:
                    st.markdown(f"""
                    <div class='{container_css}'>
                    監控中...<br>
                    目標: {bot['code']}<br>
                    條件: < {bot['price']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"🔴 停止任務 #{i+1}", key=f"stop_{i}", use_container_width=True):
                        st.session_state.bot_instances[i]['active'] = False
                        msg = f"\n【任務結束】\n代號: {bot['code']}\n已手動停止監控。"
                        if st.session_state.line_token:
                            engine.send_line_notify(st.session_state.line_token, msg)
                        st.rerun()

# ==========================================
# 6. 主程式進入點
# ==========================================
with st.sidebar:
    st.title("🕵️ 股市特務 X")
    st.markdown("---")
    module = st.radio("特務功能導航", ["📊 股市情報站", "🤖 股市特務 X"])
    st.markdown("---")
    if st.button("清除快取"):
        st.cache_data.clear()
        st.rerun()

if module == "📊 股市情報站":
    render_dashboard()
elif module == "🤖 股市特務 X":
    render_bot()
