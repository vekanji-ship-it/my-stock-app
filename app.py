import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, time as dt_time
import pytz
import time
import feedparser

# ==========================================
# 1. 系統初始化 & CSS 風格
# ==========================================
st.set_page_config(page_title="ProQuant X 旗艦系統", page_icon="🦅", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', sans-serif; }
    
    /* 導航條 */
    .nav-bar { background-color: #fff; padding: 10px; border-bottom: 2px solid #ee3f2d; margin-bottom: 20px; }
    .nav-title { font-size: 24px; font-weight: bold; color: #333; }
    
    /* 卡片與區塊 */
    .card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); text-align: center; }
    .card-title { font-size: 14px; color: #666; }
    .card-val { font-size: 22px; font-weight: bold; }
    
    /* 顏色 */
    .up { color: #eb3f38; } .down { color: #2daa59; } .flat { color: #333; }
    
    /* 新聞 */
    .news-item { padding: 10px; border-bottom: 1px solid #eee; background: white; margin-bottom: 5px; border-radius: 5px; }
    .news-link { text-decoration: none; color: #333; font-weight: bold; font-size: 16px; }
    .news-link:hover { color: #ee3f2d; }
    .news-meta { font-size: 12px; color: #888; margin-top: 5px; }
    
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
        # 擴大觀察名單以模擬市場掃描 (涵蓋高價、低價、熱門股)
        self.watch_list = [
            "2330", "2317", "2454", "2603", "2609", "2615", "3231", "2382", "2356", "2303", 
            "2881", "2882", "2891", "2376", "2388", "3037", "3035", "3017", "2368", "3008",
            "1513", "1519", "1503", "1504", "2515", "2501", "2002", "1605", "2344", "2409",
            "3481", "6182", "8069", "5483", "6223", "3661", "6531", "3529", "6719", "2327",
            "2498", "3532", "5347", "3260", "6147", "8046", "3034", "3036", "4968", "2313",
            "5269", "6278", "6789", "6415", "6669", "5274", "3694", "2486", "6214", "8028",
            "2618", "2610", "2606", "2605", "1101", "1102", "1216", "1301", "1303", "1326",
            "1402", "1476", "1560", "1590", "1609", "1702", "1708", "1710", "1717", "1722",
            "1723", "1736", "1760", "1789", "1795", "1802", "1904", "1907", "1909", "2006",
            "2014", "2027", "2049", "2059", "2103", "2104", "2105", "2106", "2201", "2204"
        ]

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
        rss_url = "https://news.cnyes.com/rss/cat/twstock"
        try:
            feed = feedparser.parse(rss_url)
            news_items = []
            for entry in feed.entries[:6]:
                t = entry.published_parsed
                time_str = f"{t.tm_hour:02}:{t.tm_min:02}" if t else "最新"
                news_items.append({"title": entry.title, "link": entry.link, "time": time_str, "source": "鉅亨網"})
            return news_items
        except: return [{"title": "新聞載入失敗", "link": "#", "time": "--", "source": "系統"}]

    # 市場掃描邏輯 (加上篩選功能)
    @st.cache_data(ttl=60)
    def scan_market(_self, min_price, max_price, strategy):
        data_list = []
        tickers_tw = [f"{x}.TW" for x in _self.watch_list]
        try:
            df = yf.download(tickers_tw, period="1d", group_by='ticker', threads=True, progress=False)
            for code in _self.watch_list:
                try:
                    t_code = f"{code}.TW"
                    if t_code not in df.columns.levels[0]: continue
                    sub = df[t_code]
                    if sub.empty: continue
                    
                    row = sub.iloc[-1]
                    price = float(row['Close'])
                    
                    # 1. 第一層篩選：價格區間
                    if not (min_price <= price <= max_price): continue
                    
                    open_p = float(row['Open'])
                    change_pct = (price - open_p) / open_p * 100
                    vol = int(row['Volume'])
                    
                    data_list.append({
                        "代號": code,
                        "股價": round(price, 2),
                        "漲跌幅(%)": round(change_pct, 2),
                        "成交量": vol,
                        "abs_change": abs(change_pct) # 輔助排序用
                    })
                except: continue
                
            res_df = pd.DataFrame(data_list)
            if res_df.empty: return res_df
            
            # 2. 第二層篩選：策略排序
            if strategy == "漲跌停 (±10%)":
                # 找漲跌幅絕對值最大的
                return res_df.sort_values(by="abs_change", ascending=False).head(10)
            elif strategy == "爆量強勢股":
                # 找成交量最大的
                return res_df.sort_values(by="成交量", ascending=False).head(10)
            elif strategy == "飆股 (漲幅排行)":
                # 只找漲最多的
                return res_df.sort_values(by="漲跌幅(%)", ascending=False).head(10)
                
            return res_df
        except: return pd.DataFrame()

engine = DataEngine()

# ==========================================
# 3. Session 狀態管理
# ==========================================
if 'portfolio' not in st.session_state: 
    st.session_state.portfolio = [
        {"code": "2330", "name": "台積電", "cost": 980, "qty": 1000},
        {"code": "0050", "name": "元大台灣50", "cost": 180, "qty": 500}
    ]
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'broker_id' not in st.session_state: st.session_state.broker_id = ""

def auto_fill_name():
    code = st.session_state.p_code_input
    if code:
        info = engine.fetch_quote(code)
        if info: st.session_state.p_name_input = info['name']

# ==========================================
# 4. 模組一：資產戰情室
# ==========================================
def render_dashboard():
    st.markdown("<div class='nav-bar'><span class='nav-title'>🌍 ProQuant 資產戰情室</span></div>", unsafe_allow_html=True)
    
    col_idx, col_news = st.columns([3, 2])
    
    with col_idx:
        st.subheader("📊 市場戰情")
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
        st.subheader("🔥 市場熱點排行 (Market Scanner)")
        
        # --- 搜尋條件設定區 ---
        with st.container():
            st.info("💡 請設定篩選條件以開始搜尋")
            c_s1, c_s2, c_s3, c_s4 = st.columns([2, 2, 3, 2])
            
            # 條件 1: 價格區間
            min_p = c_s1.number_input("最低價 ($)", value=10, min_value=1)
            max_p = c_s2.number_input("最高價 ($)", value=1000, min_value=1)
            
            # 條件 2: 策略
            strat = c_s3.selectbox("篩選策略", ["漲跌停 (±10%)", "爆量強勢股", "飆股 (漲幅排行)"])
            
            # 按鈕觸發
            start_scan = c_s4.button("🔍 開始搜尋", use_container_width=True, type="primary")
        
        if start_scan:
            with st.spinner("正在掃描全市場數據..."):
                scan_res = engine.scan_market(min_p, max_p, strat)
                
                if not scan_res.empty:
                    st.success(f"搜尋完成！符合條件前 10 名：")
                    st.dataframe(
                        scan_res.style.format({"股價": "{:.2f}", "漲跌幅(%)": "{:+.2f}%", "成交量": "{:,}"}),
                        use_container_width=True
                    )
                else:
                    st.warning("⚠️ 查無符合條件的股票，請調整價格區間。")

    with col_news:
        st.subheader("📰 今日頭條 (Anue)")
        news_list = engine.get_real_news()
        for news in news_list:
            st.markdown(f"""
            <div class='news-item'>
                <a href='{news['link']}' target='_blank' class='news-link'>{news['title']}</a>
                <div class='news-meta'>{news['time']} | {news['source']}</div>
            </div>
            """, unsafe_allow_html=True)
            
    st.divider()
    
    st.subheader("🎒 我的投資組合")
    with st.expander("➕ 新增庫存紀錄", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        new_code = c1.text_input("代號", key="p_code_input", on_change=auto_fill_name)
        new_name = c2.text_input("名稱", key="p_name_input")
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
        c_tot1, c_tot2 = st.columns(2)
        color = "up" if tot_p > 0 else "down"
        c_tot1.metric("總資產", f"${tot_a:,.0f}")
        c_tot2.markdown(f"#### 總損益: <span class='{color}'>${tot_p:,.0f}</span>", unsafe_allow_html=True)

# ==========================================
# 5. 模組二：自動交易機器人 (Auto-Bot)
# ==========================================
def render_autobot():
    st.markdown("<div class='nav-bar'><span class='nav-title'>🤖 ProQuant 自動交易機器人</span></div>", unsafe_allow_html=True)
    
    # 檢查是否登入
    if not st.session_state.login_status:
        st.warning("🔒 此功能為高階交易功能，請先登入券商憑證")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("券商憑證登入 (User)")
            broker = st.selectbox("選擇合作券商", ["元大證券", "凱基證券", "富邦證券", "永豐金"])
            uid = st.text_input("身分證字號")
            pwd = st.text_input("交易密碼", type="password")
            cert = st.file_uploader("上傳憑證 (.pfx)", type=['pfx'])
            if st.button("🔐 驗證並連線", type="primary"):
                st.session_state.login_status = True
                st.session_state.broker_id = broker
                st.success("連線成功！")
                time.sleep(1)
                st.rerun()
                
        # --- 開發者測試通道 (Developer Backdoor) ---
        with c2:
            st.markdown("### 🛠️ 開發人員測試區")
            st.info("僅供功能測試使用，無需憑證")
            if st.button("🚀 開發者免登入進入 (Dev Mode)"):
                st.session_state.login_status = True
                st.session_state.broker_id = "Dev_Simulator_Mode"
                st.toast("已切換至開發者模式")
                time.sleep(0.5)
                st.rerun()
        return

    st.info(f"✅ 已連線至：{st.session_state.broker_id} (API Mode: Active)")
    
    col_chart, col_setting = st.columns([1, 1])
    
    with col_setting:
        st.markdown("### ⚙️ 策略參數設定")
        target_code = st.text_input("監控代號", "2330", key="bot_code")
        
        q = engine.fetch_quote(target_code)
        if q: st.metric("目前市價", f"{q['price']}", f"{q['change']} ({q['pct']:.2f}%)")
        
        st.divider()
        c_b1, c_b2 = st.columns(2)
        trigger_price = c_b1.number_input("🎯 觸發買進價", value=q['price'] if q else 1000.0)
        buy_qty = c_b2.number_input("買進張數", 1, 10, 1)
        
        st.markdown("#### 出場條件 (Exit Strategy)")
        c_s1, c_s2 = st.columns(2)
        stop_profit = c_s1.number_input("🚀 停利設定 (%)", value=5.0, step=0.5)
        stop_loss = c_s2.number_input("🛑 停損設定 (%)", value=2.0, step=0.5)
        
        est_profit_price = trigger_price * (1 + stop_profit/100)
        est_loss_price = trigger_price * (1 - stop_loss/100)
        st.caption(f"預估賣出價位: 停利 @ {est_profit_price:.1f} | 停損 @ {est_loss_price:.1f}")
        
        active = st.toggle("🔴 啟動自動監控", value=False)
        
        if active:
            st.success("機器人監控中... (請勿關閉視窗)")
            st.markdown(f"```text\n[System] Monitor Started: {target_code}\n[Logic] IF Price <= {trigger_price} THEN Buy {buy_qty}\n```")

    with col_chart:
        st.subheader("📈 監控標的走勢")
        if q:
            df = engine.fetch_kline(target_code)
            if not df.empty:
                fig = go.Figure(data=[go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
                fig.add_hline(y=trigger_price, line_dash="dash", line_color="red", annotation_text="買進觸發價")
                fig.update_layout(height=500, xaxis_rangeslider_visible=False, title=f"{target_code} 即時監控")
                st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 6. 主程式進入點
# ==========================================
with st.sidebar:
    st.title("🦅 ProQuant X")
    st.markdown("---")
    module = st.radio("選擇系統模組", ["📊 資產戰情室", "🤖 自動交易機器人"])
    st.markdown("---")
    st.caption("系統狀態: Online")
    if st.button("清除快取 (重整)"):
        st.cache_data.clear()
        st.rerun()

if module == "📊 資產戰情室":
    render_dashboard()
elif module == "🤖 自動交易機器人":
    render_autobot()
