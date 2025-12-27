import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, time as dt_time
import pytz
import time

# ==========================================
# 1. 系統初始化
# ==========================================
st.set_page_config(page_title="ProQuant X 戰情室", page_icon="🦅", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #333; font-family: 'Microsoft JhengHei', sans-serif; }
    
    /* 戰情室專用樣式 */
    .war-room-card {
        border: 1px solid #e0e0e0; padding: 15px; border-radius: 8px;
        background: #f8f9fa; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .index-val { font-size: 28px; font-weight: bold; font-family: 'Roboto'; }
    .index-name { font-size: 14px; color: #666; margin-bottom: 5px; }
    
    /* 顏色定義 */
    .up { color: #eb3f38; }
    .down { color: #2daa59; }
    .flat { color: #555555; }
    
    /* 側邊欄優化 */
    [data-testid="stSidebar"] { background-color: #1a1a1a; color: white; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] span { color: white; }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心引擎：時間與數據
# ==========================================
class MarketEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
    
    def get_market_status(self):
        now = datetime.now(self.tz)
        if now.weekday() >= 5: return "CLOSED", "休市 (週末)"
        market_open = dt_time(9, 0)
        market_close = dt_time(13, 30)
        current_time = now.time()
        
        if market_open <= current_time <= market_close:
            return "OPEN", "盤中連線"
        elif current_time < market_open:
            return "PRE", "盤前試搓"
        else:
            return "CLOSED", "已收盤"

    @st.cache_data(ttl=60)
    def fetch_data(_self, ticker, period="1d", interval="1m"):
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            if df.empty: return pd.DataFrame()
            df.reset_index(inplace=True)
            df['Date'] = df['Date'].dt.tz_localize(None)
            df.rename(columns={'Close': 'close', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Volume': 'vol'}, inplace=True)
            return df
        except:
            return pd.DataFrame()

    @st.cache_data(ttl=300) # 戰情室數據快取久一點
    def fetch_global_indices(_self):
        # 抓取重要指數：台股大盤, 櫃買(模擬), 道瓊, 那斯達克, 日經
        tickers = {
            "加權指數": "^TWII",
            "道瓊工業": "^DJI",
            "那斯達克": "^IXIC",
            "費城半導體": "^SOX",
            "日經225": "^N225"
        }
        data = {}
        for name, sym in tickers.items():
            try:
                stock = yf.Ticker(sym)
                hist = stock.history(period="5d") # 抓5天確保有資料
                if not hist.empty:
                    latest = hist.iloc[-1]['Close']
                    prev = hist.iloc[-2]['Close']
                    change = latest - prev
                    pct = (change / prev) * 100
                    data[name] = {"price": latest, "change": change, "pct": pct}
            except:
                pass
        return data

engine = MarketEngine()

# ==========================================
# 3. 狀態管理
# ==========================================
if 'balance' not in st.session_state: st.session_state.balance = 1000000
if 'orders' not in st.session_state: st.session_state.orders = []
if 'page' not in st.session_state: st.session_state.page = "戰情室" # 預設首頁

# ==========================================
# 4. 側邊欄：導航與登入
# ==========================================
with st.sidebar:
    st.title("🦅 ProQuant X")
    st.markdown("---")
    
    # 導航選單
    page = st.radio("系統模組", ["🌍 股市戰情室", "💹 個股操盤室"], index=0 if st.session_state.page=="戰情室" else 1)
    st.session_state.page = page
    
    st.markdown("---")
    st.caption("用戶資訊")
    st.info(f"權益數: ${st.session_state.balance:,.0f}")
    
    # 市場狀態顯示
    code, txt = engine.get_market_status()
    st.caption(f"市場狀態: {txt}")

# ==========================================
# 5. 頁面 A：股市戰情室 (Dashboard)
# ==========================================
if "戰情室" in page:
    st.title("🌍 全球股市戰情室")
    st.markdown("### 📊 市場概覽 (Global Overview)")
    
    # 獲取指數數據
    indices = engine.fetch_global_indices()
    
    # 顯示指數卡片 (5欄佈局)
    cols = st.columns(5)
    keys = list(indices.keys())
    
    for i, col in enumerate(cols):
        if i < len(keys):
            name = keys[i]
            data = indices[name]
            color = "up" if data['change'] > 0 else "down"
            with col:
                st.markdown(f"""
                <div class='war-room-card'>
                    <div class='index-name'>{name}</div>
                    <div class='index-val {color}'>{data['price']:,.0f}</div>
                    <div class='{color}'>{data['change']:+.0f} ({data['pct']:+.2f}%)</div>
                </div>
                """, unsafe_allow_html=True)
    
    st.divider()
    
    # 三大法人與資金流向 (由於 yfinance 抓不到台股法人，這裡用模擬數據展示介面功能)
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.subheader("💰 三大法人買賣超 (預估)")
        # 模擬數據，實際需串接 TWSE API
        investors = pd.DataFrame({
            "單位": ["外資", "投信", "自營商"],
            "買賣超 (億)": [np.random.uniform(-50, 50), np.random.uniform(-10, 20), np.random.uniform(-5, 5)]
        })
        
        for _, row in investors.iterrows():
            val = row['買賣超 (億)']
            color = "red" if val > 0 else "green"
            st.markdown(f"**{row['單位']}**: :{color}[{val:+.2f} 億]")
            st.progress(int((val + 50) / 100 * 100)) # 簡單進度條示意
            
    with c2:
        st.subheader("🔥 熱門族群資金流向")
        # 模擬板塊熱力圖
        sectors = pd.DataFrame({
            "Sector": ["半導體", "AI伺服器", "航運", "金融", "生技", "重電"],
            "Change": [1.5, 2.3, -0.8, 0.5, -1.2, 0.9],
            "Volume": [500, 300, 200, 150, 100, 80]
        })
        
        fig = go.Figure(go.Treemap(
            labels=sectors['Sector'],
            parents=["台股"] * len(sectors),
            values=sectors['Volume'],
            textinfo="label+value+percent entry",
            marker=dict(
                colors=sectors['Change'],
                colorscale='RdBu_r', # 紅漲綠跌 (Red-Blue reversed)
                midpoint=0
            )
        ))
        fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=300)
        st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 6. 頁面 B：個股操盤室 (Trading Console)
# ==========================================
elif "個股操盤" in page:
    # 這裡放入原本強大的個股操盤代碼
    
    # 1. 搜尋列
    c_search, c_status = st.columns([3, 1])
    with c_search:
        ticker = st.text_input("輸入代號", "2330.TW", key="trade_ticker")
    with c_status:
        st.write("") # Spacer
        
    # 2. 獲取數據
    status, _ = engine.get_market_status()
    # 判斷抓取週期: 盤中抓1m, 盤後抓日線
    period = "1d" if status == "OPEN" else "3mo"
    interval = "1m" if status == "OPEN" else "1d"
    
    df = engine.fetch_data(ticker, period, interval)
    
    if not df.empty:
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        chg = last['close'] - prev['close']
        pct = (chg / prev['close']) * 100
        color = "up" if chg > 0 else "down"
        
        # 看板
        st.markdown(f"""
        <div style='display:flex; align-items:flex-end;'>
            <div style='font-size:36px; font-weight:bold;'>{ticker}</div>
            <div style='margin-left:20px; font-size:42px; font-weight:bold;' class='{color}'>{last['close']:.2f}</div>
            <div style='margin-left:15px; font-size:20px;' class='{color}'>{chg:+.2f} ({pct:+.2f}%)</div>
        </div>
        """, unsafe_allow_html=True)
        
        # 圖表
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_width=[0.2, 0.8], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='K'), row=1, col=1)
        
        # 均線
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA5'], line=dict(color='orange', width=1), name='MA5'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], line=dict(color='#2196f3', width=1), name='MA20'), row=1, col=1)
        
        # 量
        colors = ['#eb3f38' if c >= o else '#2daa59' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df['Date'], y=df['vol'], marker_color=colors), row=2, col=1)
        
        fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)
        
        # 下單區 (含自動交易設定)
        st.divider()
        col_trade, col_robot = st.columns(2)
        
        with col_trade:
            st.subheader("⚡ 下單交易")
            type_ = st.radio("類型", ["現股", "當沖", "零股"], horizontal=True)
            t_qty = st.number_input("數量", 1, 100, 1)
            t_price = st.number_input("價格", value=last['close'])
            if st.button("買進", use_container_width=True):
                st.session_state.orders.append(f"買進 {ticker} {t_qty}張 @ {t_price}")
                st.success("委託成功")
                
        with col_robot:
            st.subheader("🤖 自動機器人設定")
            st.selectbox("監控策略", ["KD 金叉", "RSI 超賣", "突破前高"])
            c1, c2 = st.columns(2)
            c1.number_input("單筆張數", 1, 10, 1)
            c2.number_input("最大加碼筆數", 1, 5, 3)
            st.toggle("啟動自動監控")
            
    else:
        st.error("查無資料，請確認代號")
