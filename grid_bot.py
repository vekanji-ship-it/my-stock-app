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
st.set_page_config(page_title="股市特務 X - 終極版", page_icon="📈", layout="wide")

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
    
    /* 狀態顏色 */
    .up { color: #d32f2f; font-weight: bold; } 
    .down { color: #2e7d32; font-weight: bold; }
    
    /* 網格表格 */
    .grid-row { padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
    .grid-active { background: #e3f2fd; border-left: 5px solid #2196f3; font-weight: bold; }
    
    /* 標籤樣式 */
    .tag-sell { background-color: #ffebee; color: #c62828; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .tag-buy { background-color: #e8f5e9; color: #2e7d32; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .tag-wait { background-color: #f5f5f5; color: #616161; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎 (完整版)
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        self.name_map = {
            "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2603": "長榮", "0050": "元大台灣50",
            "0056": "元大高股息", "00878": "國泰永續高股息", "00632R": "元大台灣50反1",
            "^TWII": "加權指數", "^TWOII": "櫃買指數", "^DJI": "道瓊", "^IXIC": "那斯達克", "^SOX": "費半"
        }
        self.watch_list = ["2330", "2317", "2454", "2603", "2609", "2615", "3231", "2382", "2356", "2303"]

    def get_stock_name(self, ticker):
        clean = ticker.replace('.TW', '')
        return self.name_map.get(clean, ticker)

    @st.cache_data(ttl=60)
    def fetch_quote(_self, ticker):
        if not ticker.endswith('.TW') and not ticker.startswith('^') and ticker.isdigit(): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period='1d', interval='1m')
            if df.empty: df = stock.history(period='5d', interval='1d')
            if df.empty: return None
            
            last = df.iloc[-1]
            price = float(last['Close'])
            change = 0.0
            pct = 0.0
            if len(df) > 1:
                prev = df.iloc[-2]['Close']
                change = price - prev
                pct = (change / prev) * 100
            
            return {
                "name": _self.get_stock_name(ticker.replace('.TW', '')),
                "price": price, "change": change, "pct": pct, "vol": last.get('Volume', 0),
                "open": last['Open'], "high": last['High'], "low": last['Low']
            }
        except: return None

    @st.cache_data(ttl=300)
    def fetch_stock_profile(_self, ticker):
        if not ticker.endswith('.TW') and ticker.isdigit(): ticker += '.TW'
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
        targets = ["^TWII", "^TWOII", "^DJI", "^IXIC", "^SOX"]
        res = {}
        for sym in targets:
            q = _self.fetch_quote(sym)
            if q: res[q['name']] = q
        return res

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

    @st.cache_data(ttl=60)
    def scan_market(_self, min_p, max_p, strategy):
        # 簡易模擬掃描，實際應抓取全市場，這裡演示用 Watch list
        data_list = []
        try:
            for code in _self.watch_list:
                q = _self.fetch_quote(code)
                if q and min_p <= q['price'] <= max_p:
                    data_list.append({
                        "代號": code, "名稱": q['name'], "股價": q['price'], 
                        "漲跌幅": q['pct'], "成交量": q['vol'], "abs_change": abs(q['pct'])
                    })
            res = pd.DataFrame(data_list)
            if res.empty: return res
            if strategy == "漲跌停 (±10%)": return res.sort_values(by="abs_change", ascending=False)
            elif strategy == "爆量強勢股": return res.sort_values(by="成交量", ascending=False)
            elif strategy == "飆股 (漲幅排行)": return res.sort_values(by="漲跌幅", ascending=False)
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
    
    @st.cache_data(ttl=300)
    def get_real_news(_self):
        rss_url = "https://news.google.com/rss/search?q=台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        news_items = []
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:5]:
                t = entry.published_parsed
                time_str = f"{t.tm_hour:02}:{t.tm_min:02}" if t else "最新"
                news_items.append({"title": entry.title, "link": entry.link, "time": time_str, "source": "News"})
        except: pass
        if not news_items: return [{"title": "系統連線中...", "link": "#", "time": "--", "source": "系統"}]
        return news_items

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

    fig.update_layout(title=title, height=400, xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=30,b=10), paper_bgcolor='white', plot_bgcolor='white')
    fig.update_xaxes(showgrid=True, gridcolor='#eee')
    fig.update_yaxes(showgrid=True, gridcolor='#eee')
    return fig

# 費用計算
def calculate_fee(price, qty, action, discount):
    amount = price * qty * 1000 
    fee_rate = 0.001425
    tax_rate = 0.003
    raw_fee = amount * fee_rate
    discounted_fee = int(raw_fee * discount)
    
    if action == "BUY":
        return int(amount + discounted_fee), discounted_fee, 0
    else: 
        tax = int(amount * tax_rate)
        return int(amount - discounted_fee - tax), discounted_fee, tax

# ==========================================
# 3. Session 狀態管理
# ==========================================
# Dashboard 狀態
if 'portfolio' not in st.session_state: st.session_state.portfolio = [{"code": "2330", "name": "台積電", "cost": 980, "qty": 1000}]
# Grid Bot 狀態
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'broker_name' not in st.session_state: st.session_state.broker_name = ""
if 'user_role' not in st.session_state: st.session_state.user_role = "訪客"
if 'balance' not in st.session_state: st.session_state.balance = 500000 
if 'fee_discount' not in st.session_state: st.session_state.fee_discount = 0.6 

# ==========================================
# 4. 模組：股市情報站 (Dashboard) - 功能全開版
# ==========================================
def render_dashboard():
    st.markdown(f"""
    <div class='nav-bar'>
        <span class='nav-title'>📊 股市情報站</span>
        <span class='nav-user'>👤 一般會員</span>
    </div>""", unsafe_allow_html=True)
    
    col_main, col_news = st.columns([3, 2])
    
    with col_main:
        # A. 大盤行情 (回歸了！)
        st.subheader("🌍 市場行情")
        indices = engine.fetch_indices()
        c_grid = st.columns(4)
        idx = 0
        for name, data in indices.items():
            if idx < 4:
                color = "up" if data['change'] > 0 else "down"
                with c_grid[idx]:
                    st.markdown(f"""
                    <div class='card' style='padding:10px; text-align:center;'>
                        <div style='font-size:14px; color:#888;'>{name}</div>
                        <div style='font-size:18px; font-weight:bold;' class='{color}'>{data['price']:,.0f}</div>
                        <div style='font-size:12px;' class='{color}'>{data['pct']:+.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
                idx += 1
        
        st.divider()

        # B. 全方位偵查 (功能全開：含分頁、K線切換)
        st.subheader("🔎 全方位個股偵查")
        ticker = st.text_input("輸入代號 (例如 2330)", "2330")
        q = engine.fetch_quote(ticker)
        profile = engine.fetch_stock_profile(ticker)
        
        if q:
            c = "up" if q['change'] > 0 else "down"
            st.markdown(f"""
            <div class='card'>
                <span style='font-size:28px; font-weight:bold;' class='{c}'>{q['name']} {q['price']}</span>
                <span style='font-size:18px; margin-left:10px;' class='{c}'>{q['change']:+.2f} ({q['pct']:+.2f}%)</span>
                <div style='color:#666; font-size:14px;'>成交量: {q['vol']:,} | 開: {q['open']} 高: {q['high']} 低: {q['low']}</div>
            </div>
            """, unsafe_allow_html=True)

            tab1, tab2, tab3 = st.tabs(["📈 技術分析", "📋 基本面", "🔗 外部連結"])
            
            with tab1:
                # K線切換 (回歸了！)
                k_type = st.radio("週期", ["日K", "週K", "月K"], horizontal=True, label_visibility="collapsed")
                if k_type == "日K": k_inv, k_prd = "1d", "3mo"
                elif k_type == "週K": k_inv, k_prd = "1wk", "1y"
                else: k_inv, k_prd = "1mo", "5y"
                
                df_k = engine.fetch_kline(ticker, interval=k_inv, period=k_prd)
                if not df_k.empty:
                    st.plotly_chart(plot_chart(df_k, f"{q['name']} {k_type}"), use_container_width=True)
            
            with tab2:
                if profile:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("本益比", profile['pe'])
                    c2.metric("EPS", profile['eps'])
                    c3.metric("殖利率", f"{profile['yield']:.2f}%" if profile['yield'] != 'N/A' else 'N/A')
                    st.caption(f"產業: {profile['sector']} | 市值: {profile['marketCap']}")
                else: st.info("無基本面資料")
            
            with tab3:
                anue_url = f"https://stock.cnyes.com/market/TWS:{ticker}:STOCK"
                st.link_button("鉅亨網 (個股詳情)", anue_url)

        st.divider()

        # C. 熱點掃描 (回歸了！)
        with st.expander("🔥 市場熱點排行 (Scanner)", expanded=False):
            c1, c2, c3 = st.columns([1, 1, 1])
            min_p = c1.number_input("最低價", 10)
            max_p = c2.number_input("最高價", 1000)
            strat = c3.selectbox("策略", ["飆股 (漲幅排行)", "爆量強勢股"])
            if st.button("開始掃描"):
                res = engine.scan_market(min_p, max_p, strat)
                st.dataframe(res, use_container_width=True)

    with col_news:
        # D. 新聞 & 庫存
        st.subheader("📰 即時新聞")
        news = engine.get_real_news()
        for n in news:
            st.markdown(f"<div class='card' style='padding:10px;'><a href='{n['link']}' target='_blank' style='text-decoration:none;font-weight:bold;'>{n['title']}</a><br><small>{n['time']} | {n['source']}</small></div>", unsafe_allow_html=True)
        
        st.divider()
        st.subheader("🎒 我的庫存")
        # 簡易庫存管理 (回歸了！)
        if st.session_state.portfolio:
            p_data = []
            for item in st.session_state.portfolio:
                pq = engine.fetch_quote(item['code'])
                curr = pq['price'] if pq else 0
                prof = (curr - item['cost']) * item['qty']
                p_data.append({"名稱": item['name'], "現價": curr, "損益": prof})
            st.dataframe(pd.DataFrame(p_data), use_container_width=True)
            
        with st.expander("➕ 新增"):
             pc = st.text_input("代號", key="p_c")
             pco = st.number_input("成本", key="p_co")
             pq = st.number_input("股數", 1000, key="p_q")
             if st.button("加入"):
                 st.session_state.portfolio.append({"code": pc, "name": pc, "cost": pco, "qty": pq})
                 st.rerun()

# ==========================================
# 5. 模組：網格戰神 (Grid Bot) - 2.0 Pro版
# ==========================================
def render_grid_bot():
    # 權限檢查
    if not st.session_state.login_status:
        st.markdown("<div class='nav-bar'><span class='nav-title'>⚡ 網格戰神 (鎖定中)</span></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.warning("🔒 此功能需要券商權限")
            broker = st.selectbox("選擇券商", ["元大證券", "凱基證券", "富邦證券"])
            pwd = st.text_input("憑證密碼", type="password")
            if st.button("🔐 安全登入", use_container_width=True):
                if pwd: 
                    st.session_state.login_status = True
                    st.session_state.broker_name = broker
                    st.session_state.user_role = "VIP會員 (模擬倉)"
                    st.rerun()
                else: st.error("請輸入密碼")
            st.markdown("</div>", unsafe_allow_html=True)
        return

    # 已登入介面
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

    # 設定區
    with st.expander("🔧 戰略指揮中心 (參數設定)", expanded=True):
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            st.markdown("#### 1. 標的與資金")
            ticker = st.text_input("交易代號", "00632R", key="g_ticker")
            q = engine.fetch_quote(ticker)
            cur_price = q['price'] if q else 10.0
            if q: st.success(f"現價: {cur_price}")
            
            invest_amt = st.number_input("投入金額", value=100000, step=10000)
            fee_dis = st.number_input("手續費折數", value=st.session_state.fee_discount, min_value=0.1, max_value=1.0, step=0.01)
            st.session_state.fee_discount = fee_dis

        with c2:
            st.markdown("#### 2. 網格區間")
            upper = st.number_input("上限 (天花板)", value=float(cur_price * 1.05))
            lower = st.number_input("下限 (地板)", value=float(cur_price * 0.95))
            grid_num = st.number_input("網格數", value=10, min_value=2)

        with c3:
            st.markdown("#### 3. 安全機制")
            take_profit_pct = st.number_input("突破上限 N% 全賣", value=2.0)
            stop_loss_pct = st.number_input("跌破下限 N% 全賣", value=3.0)
            is_sim = st.toggle("啟用模擬下單模式", value=True)

    # 計算與顯示
    if upper > lower:
        diff = upper - lower
        step = diff / grid_num
        levels = sorted([lower + (i * step) for i in range(grid_num + 1)], reverse=True)
        
        # 安全警告
        safety_msg = ""
        safety_alert = False
        if cur_price > upper * (1 + take_profit_pct/100):
            safety_msg = f"🚨 價格飆漲 ({cur_price})！建議全數停利 (ALL SELL)"
            safety_alert = True
        elif cur_price < lower * (1 - stop_loss_pct/100):
            safety_msg = f"🚨 價格崩跌 ({cur_price})！建議全數停損 (STOP LOSS)"
            safety_alert = True

        col_chart, col_list = st.columns([2, 1])
        
        with col_chart:
            st.subheader("📉 戰況圖表")
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            if safety_alert: st.error(safety_msg)
            df_g = engine.fetch_kline(ticker, interval="60m", period="1mo")
            if not df_g.empty:
                st.plotly_chart(plot_chart(df_g, f"網格間距: {step:.2f}", levels, cur_price, upper, lower), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with col_list:
            st.subheader("📋 指令表")
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            
            can_buy_amt = st.session_state.balance if is_sim else invest_amt
            container = st.container(height=400)
            curr_zone_idx = -1
            for i in range(len(levels)-1):
                if levels[i] >= cur_price >= levels[i+1]: curr_zone_idx = i; break
            
            with container:
                if safety_alert:
                    st.error(safety_msg)
                else:
                    for i, p in enumerate(levels):
                        action = "WAIT"; css_tag = "tag-wait"; qty = 1000
                        if p > cur_price: action = "SELL"; css_tag = "tag-sell"
                        elif p < cur_price: action = "BUY"; css_tag = "tag-buy"
                        
                        est_amt, fee, tax = calculate_fee(p, qty/1000, action, st.session_state.fee_discount)
                        
                        row_style = "grid-row"
                        if i == curr_zone_idx or i == curr_zone_idx + 1: row_style += " grid-active"
                        
                        info_txt = f"<span style='font-size:11px; color:#888;'>預估淨額: ${est_amt:,}</span>"
                        if action == "BUY" and est_amt > can_buy_amt:
                            action = "餘額不足"; css_tag = "tag-wait"; info_txt = "<span style='color:red; font-size:11px'>需儲值</span>"

                        st.markdown(f"""
                        <div class='{row_style}'>
                            <div><div style='font-weight:bold;'>${p:.2f}</div>{info_txt}</div>
                            <div style='text-align:right;'><span class='{css_tag}'>{action}</span><br><span style='font-size:10px;'>費: ${fee}</span></div>
                        </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            # LINE 通知
            st.markdown("#### 📢 LINE 通知")
            l_token = st.text_input("Token", type="password", key="l_t")
            l_uid = st.text_input("UID", key="l_u")
            if st.button("📤 發送報告"):
                 if l_token: 
                     msg = f"【網格報告】\n標的: {ticker}\n現價: {cur_price}\n餘額: {st.session_state.balance}"
                     if engine.send_line_push(l_token, l_uid, msg): st.success("已發送")
                     else: st.error("發送失敗")

# ==========================================
# 6. 主程式導航
# ==========================================
with st.sidebar:
    st.title("🛡️ 股市特務 X")
    st.caption("Ultimate Ver.")
    st.markdown("---")
    
    if st.session_state.login_status:
        st.success(f"已登入: {st.session_state.broker_name}")
        if st.button("登出"): st.session_state.login_status = False; st.rerun()
    
    module = st.radio("功能導航", ["📊 股市情報站", "⚡ 網格戰神"])
    st.markdown("---")
    if st.button("清除快取"): st.cache_data.clear(); st.rerun()

if module == "📊 股市情報站":
    render_dashboard()
elif module == "⚡ 網格戰神":
    render_grid_bot()
