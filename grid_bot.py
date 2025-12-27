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
# 1. 系統初始化 & CSS 風格 (保留您原本的設定)
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
    
    /* 個股儀表板標頭 */
    .stock-header { background: white; padding: 20px; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .stock-price-lg { font-size: 36px; font-weight: bold; }
    .stock-meta { color: #666; font-size: 14px; }
    .up { color: #d32f2f; } .down { color: #2e7d32; }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎 (保留您原本的設定)
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        # 內建台股名稱翻譯字典
        self.name_map = {
            "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2603": "長榮", "2609": "陽明",
            "2615": "萬海", "3231": "緯創", "2382": "廣達", "2356": "英業達", "2303": "聯電",
            "2881": "富邦金", "2882": "國泰金", "2891": "中信金", "2376": "技嘉", "2388": "威盛",
            "3037": "欣興", "3035": "智原", "3017": "奇鋐", "2368": "金像電", "3008": "大立光",
            "1513": "中興電", "1519": "華城", "1503": "士電", "1504": "東元", "2002": "中鋼",
            "1605": "華新", "2409": "友達", "3481": "群創", "2344": "華邦電", "2498": "宏達電",
            "6182": "合晶", "8069": "元太", "5483": "中美晶", "3661": "世芯-KY", "6531": "愛普",
            "6669": "緯穎", "5269": "祥碩", "6415": "矽力-KY", "2327": "國巨", "2308": "台達電"
        }
        self.watch_list = list(self.name_map.keys())

    def is_market_open(self):
        now = datetime.now(self.tz)
        if now.weekday() >= 5: return False
        return dt_time(9, 0) <= now.time() <= dt_time(13, 30)

    def get_stock_name(self, ticker):
        clean_ticker = ticker.replace('.TW', '')
        return self.name_map.get(clean_ticker, ticker)

    @st.cache_data(ttl=60)
    def fetch_quote(_self, ticker):
        if not ticker.endswith('.TW') and not ticker.startswith('^'): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period='1d', interval='1m')
            if df.empty:
                df = stock.history(period='5d', interval='1d')
            
            if df.empty: return None
            
            last = df.iloc[-1]
            price = float(last['Close'])
            
            change = 0.0
            pct = 0.0
            if len(df) > 1:
                prev = df.iloc[-2]['Close']
                change = price - prev
                pct = (change / prev) * 100
            
            clean_ticker = ticker.replace('.TW', '')
            display_name = _self.name_map.get(clean_ticker, clean_ticker)
            
            return {
                "name": display_name, "price": price, "change": change,
                "pct": pct, "vol": last['Volume'], 
                "open": last['Open'], "high": last['High'], "low": last['Low']
            }
        except: return None
        
    @st.cache_data(ttl=3600)
    def fetch_stock_profile(_self, ticker):
        if not ticker.endswith('.TW'): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return {
                "pe": info.get('trailingPE', 'N/A'),
                "eps": info.get('trailingEps', 'N/A'),
                "marketCap": info.get('marketCap', 'N/A'),
                "yield": info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 'N/A',
                "sector": info.get('sector', 'N/A')
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
    def fetch_kline(_self, ticker, interval="1d", period="3mo"):
        if not ticker.endswith('.TW'): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            df.reset_index(inplace=True)
            df['Date'] = df['Date'].dt.tz_localize(None)
            df.columns = [c.lower() for c in df.columns]
            return df
        except: return pd.DataFrame()

    @st.cache_data(ttl=300)
    def get_real_news(_self):
        rss_url = "https://news.google.com/rss/search?q=台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        news_items = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            response = requests.get(rss_url, headers=headers, timeout=5)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                if feed.entries:
                    for entry in feed.entries[:5]:
                        t = entry.published_parsed
                        time_str = f"{t.tm_hour:02}:{t.tm_min:02}" if t else "最新"
                        news_items.append({
                            "title": entry.title, "link": entry.link,
                            "time": time_str, "source": entry.source.title if hasattr(entry, 'source') else "Google新聞"
                        })
        except: pass
        if not news_items: return [{"title": "系統連線中...", "link": "#", "time": "--", "source": "系統"}]
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
                name = _self.name_map.get(code, code)
                data_list.append({
                    "代號": code, "名稱": name, "股價": price, "漲跌幅": change_pct, "成交量": vol,
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
# 3. Session 狀態初始化
# ==========================================
if 'portfolio' not in st.session_state: st.session_state.portfolio = [{"code": "2330", "name": "台積電", "cost": 980, "qty": 1000}]

# --- Grid Bot 專用 Session ---
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'member_tier' not in st.session_state: st.session_state.member_tier = "一般會員"
if 'broker_name' not in st.session_state: st.session_state.broker_name = ""
if 'grid_strategies' not in st.session_state: st.session_state.grid_strategies = [] # 儲存多個網格策略
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'line_uid' not in st.session_state: st.session_state.line_uid = ""

def auto_fill_name():
    code = st.session_state.p_code_input
    if code:
        info = engine.fetch_quote(code)
        if info: st.session_state.p_name_input = info['name']

def plot_chinese_chart(df, title, trigger_price=None):
    fig = go.Figure(data=[go.Candlestick(
        x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='K線',
        increasing_line_color='#d32f2f', decreasing_line_color='#2e7d32'
    )])
    fig.update_traces(hovertemplate='<b>日期</b>: %{x}<br><b>開盤</b>: %{open:.2f}<br><b>最高</b>: %{high:.2f}<br><b>最低</b>: %{low:.2f}<br><b>收盤</b>: %{close:.2f}<extra></extra>')
    if trigger_price:
        fig.add_hline(y=trigger_price, line_dash="dash", line_color="blue", annotation_text="觸發買進價")
    fig.update_layout(title=title, height=350, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="股價 (TWD)", hovermode="x unified")
    return fig

# 網格計算輔助函數
def calculate_fee_v2(price, qty, action, discount):
    amount = price * qty * 1000
    fee = int(amount * 0.001425 * discount)
    tax = int(amount * 0.003) if action == "SELL" else 0
    total = int(amount + fee) if action == "BUY" else int(amount - fee - tax)
    return total, fee, tax

# ==========================================
# 4. 模組一：股市情報站 (Dashboard) - 完全不變
# ==========================================
def render_dashboard():
    st.markdown("<div class='nav-bar'><span class='nav-title'>🕵️ 股市情報站 (Intelligence Station)</span></div>", unsafe_allow_html=True)
    
    col_main, col_news = st.columns([3, 2])
    
    with col_main:
        # A. 大盤
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
        
        # B. 個股偵查
        st.subheader("🔎 全方位個股偵查")
        c_search, c_space = st.columns([1, 2])
        ticker = c_search.text_input("輸入代號 (例如 2330)", "2330")
        
        q = engine.fetch_quote(ticker)
        profile = engine.fetch_stock_profile(ticker)
        
        if q:
            color_cls = "up" if q['change'] > 0 else "down"
            st.markdown(f"""
            <div class='stock-header'>
                <span class='stock-price-lg {color_cls}'>{q['price']}</span>
                <span class='stock-meta {color_cls}' style='margin-left:10px; font-size:20px;'>{q['change']:+.2f} ({q['pct']:+.2f}%)</span>
                <div class='stock-meta'>代號: {ticker} | 名稱: {q['name']} | 成交量: {q['vol']:,}</div>
            </div>
            """, unsafe_allow_html=True)
            
            tab1, tab2, tab3 = st.tabs(["📈 技術走勢", "📋 基本資料", "🔗 深層數據 (Anue)"])
            
            with tab1:
                # === K 線週期切換 ===
                c_k_opt, c_k_void = st.columns([1, 4])
                k_type = c_k_opt.radio("K線週期", ["日K", "週K", "月K"], horizontal=True, label_visibility="collapsed")
                
                if k_type == "日K": k_inv, k_prd = "1d", "3mo"
                elif k_type == "週K": k_inv, k_prd = "1wk", "1y"
                else: k_inv, k_prd = "1mo", "5y"
                
                df_k = engine.fetch_kline(ticker, interval=k_inv, period=k_prd)
                
                if not df_k.empty:
                    st.plotly_chart(plot_chinese_chart(df_k, f"{q['name']} ({ticker}) - {k_type}線圖"), use_container_width=True, key="dash_chart")
                else:
                    st.warning("查無此週期 K 線資料")
            
            with tab2:
                if profile:
                    c_p1, c_p2, c_p3 = st.columns(3)
                    c_p1.metric("本益比 (PE)", f"{profile['pe']}")
                    c_p2.metric("每股盈餘 (EPS)", f"{profile['eps']}")
                    c_p3.metric("殖利率 (%)", f"{profile['yield']:.2f}%" if profile['yield'] != 'N/A' else 'N/A')
                    st.caption(f"產業: {profile['sector']} | 市值: {profile['marketCap']}")
                else:
                    st.info("暫無基本資料")

            with tab3:
                st.info(f"🔒 {q['name']} ({ticker}) 深層數據傳送門 (點擊直達鉅亨網)：")
                anue_base = f"https://stock.cnyes.com/market/TWS:{ticker}:STOCK"
                col_btn1, col_btn2, col_btn3 = st.columns(3)
                col_btn1.link_button("🏦 三大法人買賣超", f"{anue_base}/institutional", use_container_width=True)
                col_btn2.link_button("📉 融資融券餘額", f"{anue_base}/margin", use_container_width=True)
                col_btn3.link_button("📑 營收與財報", f"{anue_base}/financials", use_container_width=True)
                
        st.divider()
        
        # C. 熱點排行
        st.subheader("🔥 市場熱點排行 (Scanner)")
        with st.container():
            st.info("💡 請設定條件以開始搜尋")
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
        st.caption("點擊標題開啟新視窗")
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
# 5. 模組二：當沖網格戰神 (Grid Bot) - 全新改寫
# ==========================================
def render_grid_bot():
    TIER_LIMITS = {"一般會員": 1, "小資會員": 3, "大佬會員": 5}

    # === 1. 登入檢查 ===
    if not st.session_state.login_status:
        st.markdown("<div class='nav-bar'><span class='nav-title'>⚡ 網格戰神 (鎖定中)</span></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("<div class='bot-card' style='text-align:center;'>", unsafe_allow_html=True)
            st.markdown("### 🔒 模擬登入系統")
            st.info("請先登入以使用當沖網格功能")
            
            with st.form("sim_login_form"):
                broker = st.selectbox("選擇模擬券商", ["元大證券", "凱基證券", "富邦證券"])
                tier = st.selectbox("會員等級", ["一般會員", "小資會員", "大佬會員"])
                acc = st.text_input("帳號 (任意輸入)")
                pwd = st.text_input("密碼 (任意輸入)", type="password")
                
                if st.form_submit_button("🚀 登入"):
                    if pwd:
                        st.session_state.login_status = True
                        st.session_state.member_tier = tier
                        st.session_state.broker_name = broker
                        st.rerun()
                    else:
                        st.error("請輸入密碼")
            st.markdown("</div>", unsafe_allow_html=True)
        return

    # === 2. 登入後介面 ===
    limit = TIER_LIMITS[st.session_state.member_tier]
    used = len(st.session_state.grid_strategies)
    
    st.markdown(f"""
    <div class='nav-bar'>
        <span class='nav-title'>⚡ 網格戰神 | {st.session_state.broker_name}</span>
        <div style='float:right; font-size:14px; margin-top:5px;'>
            👤 {st.session_state.member_tier} (使用額度: {used}/{limit})
        </div>
    </div>""", unsafe_allow_html=True)

    # 全域 LINE 設定
    with st.expander("📢 LINE 通知設定 (全域 Token)", expanded=False):
        c1, c2 = st.columns(2)
        st.session_state.line_token = c1.text_input("Line Token", st.session_state.line_token, type="password")
        st.session_state.line_uid = c2.text_input("User ID", st.session_state.line_uid)

    # 新增策略區塊
    if used < limit:
        with st.expander("➕ 新增網格監控", expanded=True):
            with st.form("add_grid"):
                c1, c2, c3, c4, c5 = st.columns(5)
                nc = c1.text_input("代號", "00632R")
                nu = c2.number_input("上限(賣)", 100.0)
                nl = c3.number_input("下限(買)", 80.0)
                ng = c4.number_input("格數", 10, min_value=2)
                nd = c5.number_input("手續費折數", 0.6, step=0.01)
                
                if st.form_submit_button("💾 加入監控"):
                    st.session_state.grid_strategies.append({
                        "code": nc, "upper": nu, "lower": nl, "grids": ng, "disc": nd
                    })
                    st.rerun()
    else:
        st.warning(f"⚠️ 已達 {st.session_state.member_tier} 額度上限 ({limit}筆)，無法新增。")

    # 監控列表
    st.markdown("### 📋 監控中策略")
    if not st.session_state.grid_strategies:
        st.info("目前無監控策略，請上方新增")

    for i, s in enumerate(st.session_state.grid_strategies):
        with st.container():
            st.markdown("<div class='bot-card'>", unsafe_allow_html=True)
            c_info, c_act = st.columns([3, 1])
            
            # 取得即時報價與計算
            q = engine.fetch_quote(s['code'])
            curr = q['price'] if q else 0
            step = (s['upper'] - s['lower']) / s['grids']
            levels = [s['lower'] + x * step for x in range(s['grids'] + 1)]
            
            near_sell = min([p for p in levels if p > curr], default=None)
            near_buy = max([p for p in levels if p < curr], default=None)
            
            with c_info:
                st.subheader(f"{s['code']} {q['name'] if q else ''} (現價: {curr})")
                st.caption(f"區間: {s['lower']} ~ {s['upper']} | 格數: {s['grids']} | 折數: {s['disc']}")
                
                col_a, col_b = st.columns(2)
                if near_sell: col_a.error(f"🔴 下一檔賣壓: {near_sell:.2f}")
                if near_buy: col_b.success(f"🟢 下一檔支撐: {near_buy:.2f}")
                
            with c_act:
                if st.button("🗑️ 刪除", key=f"del_{i}"):
                    st.session_state.grid_strategies.pop(i)
                    st.rerun()
                
                if st.button("📤 Line 通知", key=f"ln_{i}"):
                    if st.session_state.line_token:
                        # 費用試算
                        fee_b, _, _ = calculate_fee_v2(near_buy if near_buy else 0, 1, "BUY", s['disc'])
                        fee_s, _, _ = calculate_fee_v2(near_sell if near_sell else 0, 1, "SELL", s['disc'])
                        
                        msg = f"【網格快報】\n{s['code']} 現價:{curr}\n建議買進:{near_buy} (含費約${fee_b})\n建議賣出:{near_sell} (含費稅約${fee_s})"
                        
                        if engine.send_line_push(st.session_state.line_token, st.session_state.line_uid, msg):
                            st.toast("通知已發送!", icon="✅")
                        else:
                            st.error("發送失敗")
                    else:
                        st.error("請先設定 Token")
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 6. 主程式導航
# ==========================================
with st.sidebar:
    st.title("🕵️ 股市特務 X")
    st.markdown("---")
    
    if st.session_state.login_status:
        st.success(f"已登入: {st.session_state.member_tier}")
        if st.button("登出切換帳號"):
            st.session_state.login_status = False
            st.session_state.grid_strategies = []
            st.rerun()
            
    module = st.radio("導航", ["📊 股市情報站", "⚡ 網格戰神"])
    st.markdown("---")
    if st.button("清除快取"):
        st.cache_data.clear()
        st.rerun()

if module == "📊 股市情報站":
    render_dashboard()
elif module == "⚡ 網格戰神":
    render_grid_bot()
