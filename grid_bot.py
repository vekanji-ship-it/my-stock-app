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
st.set_page_config(page_title="股市特務 X - 修復版", page_icon="🛠️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', sans-serif; }
    .nav-bar { 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px; color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center;
    }
    .nav-title { font-size: 24px; font-weight: bold; }
    .nav-user { font-size: 14px; background: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 15px; }
    .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px; }
    .grid-row { padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
    .grid-active { background: #e3f2fd; border-left: 5px solid #2196f3; font-weight: bold; }
    .tag-sell { background-color: #ffebee; color: #c62828; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .tag-buy { background-color: #e8f5e9; color: #2e7d32; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .tag-wait { background-color: #f5f5f5; color: #616161; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        self.name_map = {
            "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2603": "長榮", "0050": "元大台灣50",
            "0056": "元大高股息", "00878": "國泰永續高股息", "00632R": "元大台灣50反1",
            "^TWII": "加權指數", "^TWOII": "櫃買指數", "^DJI": "道瓊", "^IXIC": "那斯達克", "^SOX": "費半"
        }
        self.watch_list = ["2330", "2317", "2454", "2603", "2609", "2615", "3231", "2382", "2356", "2303", "1513", "1519", "3035", "3037"]

    def get_stock_name(self, ticker):
        clean = ticker.replace('.TW', '')
        return self.name_map.get(clean, ticker)

    @st.cache_data(ttl=30)
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
    def scan_market(_self, strategy):
        data_list = []
        try:
            for code in _self.watch_list:
                q = _self.fetch_quote(code)
                if q:
                    data_list.append({
                        "代號": code, "名稱": q['name'], "股價": q['price'], 
                        "漲跌幅": q['pct'], "成交量": q['vol']
                    })
            res = pd.DataFrame(data_list)
            if res.empty: return res
            
            if strategy == "漲幅排行 (飆股)": return res.sort_values(by="漲跌幅", ascending=False)
            elif strategy == "爆量強勢股": return res.sort_values(by="成交量", ascending=False)
            elif strategy == "跌深反彈": return res.sort_values(by="漲跌幅", ascending=True)
            return res
        except: return pd.DataFrame()

    def send_line_push(self, token, user_id, message):
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
        data = {"to": user_id, "messages": [{"type": "text", "text": message}]}
        try:
            r = requests.post(url, headers=headers, json=data)
            return r.status_code == 200
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
    
    if upper_limit: fig.add_hline(y=upper_limit, line_color="red", line_width=2, line_dash="dash", annotation_text="停利")
    if lower_limit: fig.add_hline(y=lower_limit, line_color="green", line_width=2, line_dash="dash", annotation_text="停損")
    if current_price: fig.add_hline(y=current_price, line_color="#2196f3", line_width=1.5, annotation_text="現價")

    fig.update_layout(title=title, height=400, xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=30,b=10), paper_bgcolor='white', plot_bgcolor='white')
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
if 'portfolio' not in st.session_state: st.session_state.portfolio = [{"code": "2330", "name": "台積電", "cost": 980, "qty": 1000}]
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'broker_name' not in st.session_state: st.session_state.broker_name = ""
if 'user_role' not in st.session_state: st.session_state.user_role = "訪客"
if 'balance' not in st.session_state: st.session_state.balance = 500000 
if 'fee_discount' not in st.session_state: st.session_state.fee_discount = 0.6 
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'line_uid' not in st.session_state: st.session_state.line_uid = ""

# ==========================================
# 4. 共用模組：台股小金庫
# ==========================================
def render_treasury():
    st.markdown("### 💰 台股小金庫")
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    
    if st.session_state.portfolio:
        p_data = []
        total_profit = 0
        for item in st.session_state.portfolio:
            pq = engine.fetch_quote(item['code'])
            curr = pq['price'] if pq else item['cost'] 
            prof = (curr - item['cost']) * item['qty']
            total_profit += prof
            p_data.append({
                "代號": item['code'], "名稱": item['name'], "成本": item['cost'], 
                "現價": curr, "股數": item['qty'], "預估損益": prof
            })
        
        st.metric("庫存總損益", f"${total_profit:,.0f}", delta=total_profit)
        st.dataframe(pd.DataFrame(p_data).style.format({"成本":"{:.2f}", "現價":"{:.2f}", "預估損益":"{:.0f}"}), use_container_width=True)
    else:
        st.info("尚無庫存")

    tab_add, tab_del = st.tabs(["➕ 新增", "🗑️ 刪除"])
    
    with tab_add:
        c1, c2, c3, c4 = st.columns(4)
        pc = c1.text_input("代號", key="t_c")
        pn = c2.text_input("名稱", key="t_n")
        pco = c3.number_input("成本", min_value=0.0, key="t_co")
        pq = c4.number_input("股數", min_value=1, step=1000, key="t_q")
        if st.button("加入金庫"):
            if pc:
                if not pn:
                    q_info = engine.fetch_quote(pc)
                    pn = q_info['name'] if q_info else pc
                st.session_state.portfolio.append({"code": pc, "name": pn, "cost": pco, "qty": pq})
                st.rerun()

    with tab_del:
        if st.session_state.portfolio:
            options = [f"{i['code']} - {i['name']}" for i in st.session_state.portfolio]
            selected = st.multiselect("選擇刪除項目", options)
            if st.button("確認刪除"):
                new_p = [i for i in st.session_state.portfolio if f"{i['code']} - {i['name']}" not in selected]
                st.session_state.portfolio = new_p
                st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 5. 主頁面：股市情報站
# ==========================================
def render_dashboard():
    st.markdown(f"""
    <div class='nav-bar'>
        <span class='nav-title'>📊 股市情報站</span>
        <span class='nav-user'>👤 一般會員</span>
    </div>""", unsafe_allow_html=True)
    
    col_main, col_news = st.columns([3, 2])
    
    with col_main:
        st.subheader("🌍 市場行情")
        indices = engine.fetch_indices()
        c_grid = st.columns(4)
        idx = 0
        for name, data in indices.items():
            if idx < 4:
                color = "up" if data['change'] > 0 else "down"
                c_grid[idx].metric(name, f"{data['price']:,.0f}", f"{data['pct']:.2f}%")
                idx += 1
        
        st.divider()

        st.subheader("🔎 個股偵查")
        ticker = st.text_input("輸入代號", "2330")
        q = engine.fetch_quote(ticker)
        profile = engine.fetch_stock_profile(ticker)
        
        if q:
            c = "up" if q['change'] > 0 else "down"
            st.markdown(f"### {q['name']} {q['price']} <span class='{c}'>{q['change']:+.2f} ({q['pct']:+.2f}%)</span>", unsafe_allow_html=True)
            
            tab1, tab2, tab3 = st.tabs(["📈 技術", "📋 基本面", "🔗 外部"])
            with tab1:
                k_type = st.radio("週期", ["日K", "週K", "月K"], horizontal=True)
                if k_type == "日K": k_inv, k_prd = "1d", "3mo"
                elif k_type == "週K": k_inv, k_prd = "1wk", "1y"
                else: k_inv, k_prd = "1mo", "5y"
                df_k = engine.fetch_kline(ticker, interval=k_inv, period=k_prd)
                if not df_k.empty: st.plotly_chart(plot_chart(df_k, f"{q['name']} {k_type}"), use_container_width=True)
            with tab2:
                if profile:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("PE", profile['pe']); c2.metric("EPS", profile['eps']); c3.metric("殖利率", f"{profile['yield']:.2f}%")
                else: st.info("無資料")
            with tab3:
                st.link_button("鉅亨網", f"https://stock.cnyes.com/market/TWS:{ticker}:STOCK")

        st.divider()
        with st.expander("🔥 熱點掃描"):
             c1, c2 = st.columns([2, 1])
             strat = c1.selectbox("選擇策略", ["漲幅排行 (飆股)", "爆量強勢股", "跌深反彈"])
             if c2.button("開始掃描"):
                 res = engine.scan_market(strat)
                 st.dataframe(res, use_container_width=True)

    with col_news:
        st.subheader("📰 即時新聞")
        news = engine.get_real_news()
        for n in news:
            st.markdown(f"**[{n['title']}]({n['link']})**\n<small>{n['time']}</small>", unsafe_allow_html=True)
        st.divider()
        render_treasury()

# ==========================================
# 6. 模組：網格戰神 (徹底修復登入與顯示問題)
# ==========================================
def render_grid_bot():
    # 權限檢查：使用原生元件，避免HTML排版造成的崩潰
    if not st.session_state.login_status:
        st.markdown("### ⚡ 網格戰神 (鎖定中)")
        st.warning("🔒 安全區域：請先登入")
        
        # === 這裡改用最簡單的表單，確保一定顯示 ===
        with st.form("login_form"):
            st.selectbox("選擇券商", ["元大證券", "凱基證券", "富邦證券"])
            st.text_input("帳號 (任意)", placeholder="請輸入證券帳號")
            pwd = st.text_input("憑證密碼 (任意)", type="password")
            
            if st.form_submit_button("🔐 登入"):
                if pwd:
                    st.session_state.login_status = True
                    st.session_state.broker_name = "模擬券商"
                    st.session_state.user_role = "VIP (模擬)"
                    st.rerun()
                else:
                    st.error("請輸入密碼")
        return  # 未登入前，直接結束函數，不顯示下方內容

    # --- 以下為登入後才會顯示的內容 ---
    st.markdown(f"""
    <div class='nav-bar'>
        <div>⚡ 網格戰神 | 🏦 {st.session_state.broker_name}</div>
        <div>💰 模擬餘額: ${st.session_state.balance:,.0f}</div>
    </div>""", unsafe_allow_html=True)

    # 設定區
    with st.expander("🔧 戰略參數", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ticker = st.text_input("代號", "00632R", key="g_ticker")
            q = engine.fetch_quote(ticker)
            cur_price = q['price'] if q else 10.0
            if q: st.success(f"現價: {cur_price}")
            invest_amt = st.number_input("金額", value=100000, step=10000)
            st.session_state.fee_discount = st.number_input("手續費折數", value=st.session_state.fee_discount, step=0.01)

        with c2:
            upper = st.number_input("上限", value=float(cur_price * 1.05))
            lower = st.number_input("下限", value=float(cur_price * 0.95))
            grid_num = st.number_input("格數", value=10, min_value=2)

        with c3:
            tp = st.number_input("停利(%)", value=2.0)
            sl = st.number_input("停損(%)", value=3.0)
            is_sim = st.toggle("模擬下單", value=True)

    # 計算核心
    if upper > lower:
        diff = upper - lower
        step = diff / grid_num
        levels = sorted([lower + (i * step) for i in range(grid_num + 1)], reverse=True)
        
        col_chart, col_list = st.columns([2, 1])
        with col_chart:
            st.subheader("📉 戰況")
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            df_g = engine.fetch_kline(ticker, interval="60m", period="1mo")
            if not df_g.empty: st.plotly_chart(plot_chart(df_g, f"網格間距: {step:.2f}", levels, cur_price, upper, lower), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with col_list:
            st.subheader("📋 指令")
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            can_buy_amt = st.session_state.balance if is_sim else invest_amt
            
            container = st.container(height=300)
            with container:
                for p in levels:
                    action = "WAIT"; css = "tag-wait"; qty = 1000
                    if p > cur_price: action = "SELL"; css = "tag-sell"
                    elif p < cur_price: action = "BUY"; css = "tag-buy"
                    
                    est, fee, tax = calculate_fee(p, qty/1000, action, st.session_state.fee_discount)
                    
                    info = f"<span style='color:#888;font-size:11px'>${est:,}</span>"
                    if action=="BUY" and est > can_buy_amt: 
                        action="餘額不足"; css="tag-wait"; info="<span style='color:red;font-size:11px'>X</span>"

                    st.markdown(f"<div class='grid-row'><div><b>${p:.2f}</b> {info}</div><div><span class='{css}'>{action}</span></div></div>", unsafe_allow_html=True)
            
            # LINE 通知 (這裡絕對會顯示)
            st.markdown("---")
            st.markdown("#### 📢 LINE 通知")
            # 這裡用 session state 綁定，避免重整消失
            st.session_state.line_token = st.text_input("Line Token", type="password", value=st.session_state.line_token, key="lt_grid")
            st.session_state.line_uid = st.text_input("User ID", value=st.session_state.line_uid, key="lu_grid")
            
            if st.button("📤 發送網格報告"):
                if st.session_state.line_token:
                    msg = f"【網格戰神】\n標的: {ticker}\n現價: {cur_price}\n建議操作: {lower}~{upper}\n折數: {st.session_state.fee_discount}"
                    if engine.send_line_push(st.session_state.line_token, st.session_state.line_uid, msg):
                        st.success("已發送")
                    else:
                        st.error("發送失敗")
                else:
                    st.error("請輸入 Token")

            st.markdown("</div>", unsafe_allow_html=True)
    
    st.divider()
    render_treasury()

# ==========================================
# 7. 主程式導航
# ==========================================
with st.sidebar:
    st.title("🔥 股市特務 X")
    st.markdown("---")
    
    if st.session_state.login_status:
        st.success(f"已登入: {st.session_state.broker_name}")
        if st.button("登出 (切換帳號)"): 
            st.session_state.login_status = False
            st.rerun()
    
    module = st.radio("功能導航", ["📊 股市情報站", "⚡ 網格戰神"])
    st.markdown("---")
    if st.button("清除快取"): st.cache_data.clear(); st.rerun()

if module == "📊 股市情報站":
    render_dashboard()
elif module == "⚡ 網格戰神":
    render_grid_bot()
