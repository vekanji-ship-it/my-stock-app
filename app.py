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
# 1. 系統初始化 & CSS 風格 (特務黑科技風)
# ==========================================
st.set_page_config(page_title="股市特務 X", page_icon="🕵️", layout="wide")

st.markdown("""
    <style>
    /* 全局中文化字體 */
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', 'PingFang TC', sans-serif; }
    
    /* 導航條 */
    .nav-bar { 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px; color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .nav-title { font-size: 26px; font-weight: bold; letter-spacing: 1px; }
    
    /* 卡片優化 */
    .card { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); text-align: center; }
    .card-title { font-size: 14px; color: #666; }
    .card-val { font-size: 22px; font-weight: bold; }
    
    /* 台股紅漲綠跌 */
    .up { color: #d32f2f; } .down { color: #2e7d32; } .flat { color: #555; }
    
    /* 新聞列表 */
    .news-item { padding: 12px; border-bottom: 1px solid #eee; background: white; margin-bottom: 8px; border-radius: 8px; transition: 0.2s; }
    .news-item:hover { transform: translateX(5px); border-left: 4px solid #1e3c72; }
    .news-link { text-decoration: none; color: #333; font-weight: bold; font-size: 16px; display: block; }
    .news-link:hover { color: #1e3c72; }
    .news-meta { font-size: 12px; color: #888; margin-top: 5px; }

    /* 機器人狀態 */
    .bot-card { border: 1px solid #ddd; border-radius: 10px; padding: 15px; margin-bottom: 15px; background: white; }
    .bot-active-border { border-left: 5px solid #4caf50; }
    .bot-inactive-border { border-left: 5px solid #9e9e9e; }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        # 熱門股清單 (用於掃描)
        self.watch_list = [
            "2330", "2317", "2454", "2603", "2609", "2615", "3231", "2382", "2356", "2303", 
            "2881", "2882", "2891", "2376", "2388", "3037", "3035", "3017", "2368", "3008",
            "1513", "1519", "1503", "1504", "2515", "2501", "2002", "1605", "2344", "2409",
            "3481", "6182", "8069", "5483", "6223", "3661", "6531", "3529", "6719", "2327",
            "2498", "3532", "5347", "3260", "6147", "8046", "3034", "3036", "4968", "2313"
        ]

    # 安全機制：交易時間判斷
    def is_market_open(self):
        now = datetime.now(self.tz)
        # 週末不開盤
        if now.weekday() >= 5: return False
        # 時間 09:00 ~ 13:30
        return dt_time(9, 0) <= now.time() <= dt_time(13, 30)

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
        # 強化版 RSS 抓取 (使用 Header 模擬瀏覽器)
        rss_urls = [
            "https://news.cnyes.com/rss/cat/twstock", 
            "https://news.cnyes.com/rss/cat/headline"
        ]
        news_items = []
        headers = {'User-Agent': 'Mozilla/5.0'} # 模擬瀏覽器防止被擋
        
        for url in rss_urls:
            try:
                # 先用 requests 抓取 XML
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                    if not feed.entries: continue
                    for entry in feed.entries[:5]:
                        if any(x['link'] == entry.link for x in news_items): continue
                        t = entry.published_parsed
                        time_str = f"{t.tm_hour:02}:{t.tm_min:02}" if t else "最新"
                        news_items.append({"title": entry.title, "link": entry.link, "time": time_str, "source": "鉅亨網"})
                if len(news_items) >= 6: break
            except: pass
            
        # 備用假資料 (以防網路完全不通時 UI 壞掉)
        if not news_items:
            return [
                {"title": "台積電法說會前夕 外資押寶半導體供應鏈", "link": "#", "time": "10:30", "source": "系統備用"},
                {"title": "AI 伺服器需求爆發 廣達、緯創股價再創新高", "link": "#", "time": "10:15", "source": "系統備用"}
            ]
        return news_items

    # 搜尋功能 (價格 + 策略)
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
                
                # 條件 1: 價格
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
            
            # 條件 2: 策略
            if strategy == "漲跌停 (±10%)":
                return res.sort_values(by="abs_change", ascending=False).head(10)
            elif strategy == "爆量強勢股":
                return res.sort_values(by="成交量", ascending=False).head(10)
            elif strategy == "飆股 (漲幅排行)":
                return res.sort_values(by="漲跌幅", ascending=False).head(10)
            return res
        except: return pd.DataFrame()

    # LINE API (Messaging API)
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
# 3. Session 狀態與輔助函式
# ==========================================
if 'portfolio' not in st.session_state: st.session_state.portfolio = [{"code": "2330", "name": "台積電", "cost": 980, "qty": 1000}]
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'member_tier' not in st.session_state: st.session_state.member_tier = "一般會員"
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'line_uid' not in st.session_state: st.session_state.line_uid = ""
if 'bot_instances' not in st.session_state:
    st.session_state.bot_instances = [
        {"id": i, "active": False, "code": "2330", "price": 1000.0, "qty": 1, "profit": 5.0, "loss": 2.0} 
        for i in range(5)
    ]

def auto_fill_name():
    code = st.session_state.p_code_input
    if code:
        info = engine.fetch_quote(code)
        if info: st.session_state.p_name_input = info['name']

# 繪製中文化 K 線圖
def plot_chinese_chart(df, title, trigger_price=None):
    fig = go.Figure(data=[go.Candlestick(
        x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='日K',
        increasing_line_color='#d32f2f', decreasing_line_color='#2e7d32'
    )])
    
    # 全中文 Tooltip (這裡強制覆蓋預設的英文)
    fig.update_traces(hovertemplate='<b>日期</b>: %{x}<br><b>開盤</b>: %{open:.2f}<br><b>收盤</b>: %{close:.2f}<br><b>最高</b>: %{high:.2f}<br><b>最低</b>: %{low:.2f}')
    
    if trigger_price:
        fig.add_hline(y=trigger_price, line_dash="dash", line_color="blue", annotation_text="觸發買進價")

    fig.update_layout(
        title=title,
        height=350,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=30, b=10),
        yaxis_title="股價 (TWD)",
        hovermode="x unified"
    )
    return fig

# ==========================================
# 4. 模組一：股市情報站 (Dashboard)
# ==========================================
def render_dashboard():
    st.markdown("<div class='nav-bar'><span class='nav-title'>🕵️ 股市情報站 (Intelligence Station)</span></div>", unsafe_allow_html=True)
    
    col_main, col_news = st.columns([3, 2])
    
    with col_main:
        # A. 大盤行情
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
        
        # B. 個股偵查 (保留個股圖檔功能)
        st.subheader("🔎 個股偵查 (K線圖)")
        ticker = st.text_input("輸入代號 (例如 2330)", "2330")
        df = engine.fetch_kline(ticker)
        if not df.empty:
            # 加上唯一的 key 避免衝突
            st.plotly_chart(plot_chinese_chart(df, f"{ticker} 技術走勢"), use_container_width=True, key="search_chart")
        
        st.divider()
        
        # C. 市場熱點排行 (搜尋條件嚴格執行)
        st.subheader("🔥 市場熱點排行 (Scanner)")
        with st.container():
            st.info("💡 請設定兩大條件以開始搜尋")
            c_s1, c_s2, c_s3, c_s4 = st.columns([2, 2, 3, 2])
            
            # 條件 1: 價格
            min_p = c_s1.number_input("最低價 ($)", value=10, min_value=1)
            max_p = c_s2.number_input("最高價 ($)", value=1000, min_value=1)
            
            # 條件 2: 策略
            strat = c_s3.selectbox("篩選策略", ["漲跌停 (±10%)", "爆量強勢股", "飆股 (漲幅排行)"])
            
            # 搜尋按鈕
            if c_s4.button("🔍 開始掃描", type="primary", use_container_width=True):
                with st.spinner("正在掃描全市場數據..."):
                    res = engine.scan_market(min_p, max_p, strat)
                    if not res.empty:
                        st.success(f"搜尋完成！")
                        st.dataframe(res.style.format({"股價": "{:.2f}", "漲跌幅": "{:+.2f}%", "成交量": "{:,}"}), use_container_width=True)
                    else:
                        st.warning("查無符合條件股票")

    with col_news:
        st.subheader("📰 今日頭條 (Anue)")
        with st.spinner("正在連線鉅亨網..."):
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
    
    # 登入驗證
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

    # 安全機制檢查
    is_open = engine.is_market_open()
    status_msg = "🟢 市場開盤中 (系統運作正常)" if is_open else "🔴 休市中 (安全機制已啟動，無法下單)"
    if not is_open: st.error(f"⚠️ {status_msg}")
    else: st.success(status_msg)

    # 側邊欄設定
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

    # 機器人迴圈 (帶圖表)
    for i in range(limit):
        bot = st.session_state.bot_instances[i]
        active_css = "bot-active-border" if bot['active'] else "bot-inactive-border"
        status_txt = "🟢 監控中" if bot['active'] else "⚪ 待命"
        
        with st.expander(f"🤖 特務 #{i+1} [{bot['code']}] - {status_txt}", expanded=True):
            # 使用容器包裝樣式
            st.markdown(f"<div class='bot-card {active_css}'>", unsafe_allow_html=True)
            
            c_chart, c_ctrl = st.columns([2, 1])
            
            # 左側：圖表與參數
            with c_chart:
                # 參數列
                disabled = bot['active']
                c1, c2, c3 = st.columns(3)
                new_code = c1.text_input(f"代號 #{i+1}", bot['code'], key=f"bc_{i}", disabled=disabled)
                new_price = c2.number_input(f"觸發價 #{i+1}", value=bot['price'], key=f"bp_{i}", disabled=disabled)
                new_qty = c3.number_input(f"張數 #{i+1}", value=bot['qty'], key=f"bq_{i}", disabled=disabled)
                
                # 顯示該機器人監控的股票圖表
                df_bot = engine.fetch_kline(new_code)
                if not df_bot.empty:
                    # ⚠️ 關鍵修正：加上 key=f"bot_chart_{i}" 解決 Duplicate ID 報錯
                    st.plotly_chart(plot_chinese_chart(df_bot, f"{new_code} 監控走勢", new_price), use_container_width=True, key=f"bot_chart_{i}")
                
                if not disabled:
                    st.session_state.bot_instances[i].update({'code':new_code, 'price':new_price, 'qty':new_qty})

            # 右側：控制按鈕 (獨立開關)
            with c_ctrl:
                st.write("#### 任務控制")
                if not bot['active']:
                    # 只有開盤時間才能啟動
                    if st.button(f"🟢 啟動 #{i+1}", key=f"s_{i}", use_container_width=True, disabled=not is_open):
                        st.session_state.bot_instances[i]['active'] = True
                        msg = f"【啟動】\n標的: {new_code}\n條件: < {new_price}"
                        if st.session_state.line_token: engine.send_line_push(st.session_state.line_token, st.session_state.line_uid, msg)
                        st.rerun()
                else:
                    st.info(f"監控中...\n目標 < {bot['price']}")
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
