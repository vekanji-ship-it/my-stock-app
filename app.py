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

# ==========================================
# 1. 系統初始化 & CSS 風格
# ==========================================
st.set_page_config(page_title="ProQuant X 雙模組旗艦", page_icon="🦅", layout="wide")

st.markdown("""
    <style>
    /* 全局設定 */
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', sans-serif; }
    
    /* 頂部導航條模擬 */
    .nav-bar { background-color: #fff; padding: 10px; border-bottom: 2px solid #ee3f2d; margin-bottom: 20px; }
    .nav-title { font-size: 24px; font-weight: bold; color: #333; }
    
    /* 戰情室卡片 */
    .card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); text-align: center; }
    .card-title { font-size: 14px; color: #666; }
    .card-val { font-size: 22px; font-weight: bold; }
    
    /* 漲跌色 */
    .up { color: #eb3f38; } .down { color: #2daa59; } .flat { color: #333; }
    
    /* 新聞區塊 */
    .news-item { padding: 10px; border-bottom: 1px solid #eee; background: white; margin-bottom: 5px; border-radius: 5px; }
    .news-title { font-weight: bold; font-size: 16px; color: #333; }
    .news-meta { font-size: 12px; color: #888; margin-top: 5px; }
    
    /* 隱藏預設元件 */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎 (已修復 Cache 問題)
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')

    def get_market_status(self):
        now = datetime.now(self.tz)
        if now.weekday() >= 5: return "CLOSED"
        if dt_time(9, 0) <= now.time() <= dt_time(13, 30): return "OPEN"
        return "CLOSED"

    # 關鍵修正：將 self 改為 _self，告訴 Streamlit 忽略雜湊檢查
    @st.cache_data(ttl=60)
    def fetch_quote(_self, ticker):
        if not ticker.endswith('.TW') and not ticker.startswith('^'): ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period='5d', interval='1d')
            if df.empty: return None
            last = df.iloc[-1]
            prev = df.iloc[-2]
            return {
                "price": last['Close'], "change": last['Close'] - prev['Close'],
                "pct": (last['Close'] - prev['Close']) / prev['Close'] * 100,
                "vol": last['Volume'], "open": last['Open'], "high": last['High'], "low": last['Low']
            }
        except: return None

    # 關鍵修正：將 self 改為 _self
    @st.cache_data(ttl=300)
    def fetch_indices(_self):
        targets = {"加權指數": "^TWII", "櫃買指數": "^TWOII", "道瓊": "^DJI", "那斯達克": "^IXIC", "費半": "^SOX"}
        res = {}
        for name, sym in targets.items():
            # 這裡呼叫也要改成 _self
            q = _self.fetch_quote(sym)
            if q: res[name] = q
        return res

    # 關鍵修正：將 self 改為 _self
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

    def get_news(self):
        return [
            {"title": "台積電法說會前夕 外資押寶半導體供應鏈", "time": "10:30", "source": "鉅亨網"},
            {"title": "AI 伺服器需求爆發 廣達、緯創股價再創新高", "time": "10:15", "source": "鉅亨網"},
            {"title": "美聯準會暗示降息？ 債市資金湧入", "time": "09:50", "source": "鉅亨網"},
            {"title": "航運運價指數連三漲 長榮陽明後市看好", "time": "09:30", "source": "鉅亨網"},
            {"title": "台股開盤震盪 重電族群逆勢抗跌", "time": "09:05", "source": "鉅亨網"}
        ]

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

# ==========================================
# 4. 模組一：資產戰情室 (User Dashboard)
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
        st.subheader("🔎 個股診斷")
        ticker = st.text_input("輸入代號 (例如 2330)", "2330")
        df = engine.fetch_kline(ticker)
        
        if not df.empty:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_width=[0.2, 0.8], vertical_spacing=0.03)
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='K'), row=1, col=1)
            df['ma20'] = df['close'].rolling(20).mean()
            fig.add_trace(go.Scatter(x=df['date'], y=df['ma20'], line=dict(color='orange'), name='月線'), row=1, col=1)
            colors = ['red' if c >= o else 'green' for c, o in zip(df['close'], df['open'])]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors), row=2, col=1)
            fig.update_layout(height=400, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
    
    with col_news:
        st.subheader("📰 今日頭條 (Anue)")
        news_list = engine.get_news()
        for news in news_list:
            st.markdown(f"""
            <div class='news-item'>
                <div class='news-title'>{news['title']}</div>
                <div class='news-meta'>{news['time']} | {news['source']}</div>
            </div>
            """, unsafe_allow_html=True)
            
    st.divider()
    
    st.subheader("🎒 我的投資組合")
    with st.expander("➕ 新增庫存紀錄"):
        c1, c2, c3, c4 = st.columns(4)
        new_code = c1.text_input("代號", key="p_code")
        new_name = c2.text_input("名稱", key="p_name")
        new_cost = c3.number_input("平均成本", min_value=0.0, key="p_cost")
        new_qty = c4.number_input("股數 (張數x1000)", min_value=1, step=1000, key="p_qty")
        if st.button("加入投資組合"):
            st.session_state.portfolio.append({"code": new_code, "name": new_name, "cost": new_cost, "qty": new_qty})
            st.success("已新增")
            st.rerun()

    if st.session_state.portfolio:
        p_data = []
        total_profit = 0
        total_assets = 0
        
        for item in st.session_state.portfolio:
            q = engine.fetch_quote(item['code'])
            curr_price = q['price'] if q else item['cost']
            mkt_val = curr_price * item['qty']
            cost_val = item['cost'] * item['qty']
            profit = mkt_val - cost_val
            profit_pct = (profit / cost_val) * 100 if cost_val > 0 else 0
            
            total_assets += mkt_val
            total_profit += profit
            
            p_data.append({
                "代號": item['code'], "名稱": item['name'], "持有股數": item['qty'],
                "成本": item['cost'], "現價": f"{curr_price:.2f}",
                "損益 ($)": f"{profit:,.0f}", "報酬率 (%)": f"{profit_pct:+.2f}%"
            })
            
        st.dataframe(pd.DataFrame(p_data), use_container_width=True)
        c_tot1, c_tot2 = st.columns(2)
        color_tot = "up" if total_profit > 0 else "down"
        c_tot1.metric("總資產現值", f"${total_assets:,.0f}")
        c_tot2.markdown(f"#### 總未實現損益: <span class='{color_tot}'>${total_profit:,.0f}</span>", unsafe_allow_html=True)

# ==========================================
# 5. 模組二：自動交易機器人 (Auto-Bot)
# ==========================================
def render_autobot():
    st.markdown("<div class='nav-bar'><span class='nav-title'>🤖 ProQuant 自動交易機器人</span></div>", unsafe_allow_html=True)
    
    if not st.session_state.login_status:
        st.warning("🔒 此功能為高階交易功能，請先登入券商憑證")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("券商憑證登入")
            broker = st.selectbox("選擇合作券商", ["元大證券", "凱基證券", "富邦證券", "永豐金"])
            uid = st.text_input("身分證字號")
            pwd = st.text_input("交易密碼", type="password")
            cert = st.file_uploader("上傳憑證 (.pfx)", type=['pfx'])
            if st.button("🔐 驗證並連線", type="primary"):
                st.session_state.login_status = True
                st.session_state.broker_id = broker
                st.success("連線成功！正在讀取 API...")
                time.sleep(1)
                st.rerun()
        return

    st.info(f"✅ 已連線至：{st.session_state.broker_id} (API Mode: Active)")
    
    col_chart, col_setting = st.columns([1, 1])
    
    with col_setting:
        st.markdown("### ⚙️ 策略參數設定")
        target_code = st.text_input("監控代號", "2330", key="bot_code")
        
        q = engine.fetch_quote(target_code)
        if q:
            st.metric("目前市價", f"{q['price']}", f"{q['change']} ({q['pct']:.2f}%)")
        
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
