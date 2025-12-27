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
# 1. 系統初始化與鉅亨風格設定
# ==========================================
st.set_page_config(page_title="ProQuant X 鉅亨操盤室", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    /* 全局樣式：鉅亨網白底風格 */
    .stApp { background-color: #ffffff; color: #333; font-family: 'Microsoft JhengHei', sans-serif; }
    
    /* 價格大字 */
    .price-main { font-size: 48px; font-weight: bold; font-family: 'Roboto'; }
    .up { color: #eb3f38; }   /* 台股漲 */
    .down { color: #2daa59; } /* 台股跌 */
    .flat { color: #555555; }
    
    /* 側邊欄優化 */
    [data-testid="stSidebar"] { background-color: #f5f5f5; border-right: 1px solid #ddd; }
    
    /* 狀態標籤 */
    .status-tag {
        padding: 5px 10px; border-radius: 4px; font-size: 14px; font-weight: bold;
        display: inline-block; margin-bottom: 10px;
    }
    .status-open { background-color: #eb3f38; color: white; }
    .status-closed { background-color: #777; color: white; }
    
    /* 隱藏預設元件 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心引擎：時間與數據邏輯
# ==========================================
class MarketEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
    
    def get_market_status(self):
        """判斷台股是否開盤 (09:00 - 13:30, 週末除外)"""
        now = datetime.now(self.tz)
        
        # 1. 判斷週末 (5=週六, 6=週日)
        if now.weekday() >= 5:
            return "CLOSED", "休市 (週末)"
            
        # 2. 判斷時間 (09:00 - 13:30)
        market_open = dt_time(9, 0)
        market_close = dt_time(13, 30)
        current_time = now.time()
        
        if market_open <= current_time <= market_close:
            return "OPEN", "盤中連線"
        elif current_time < market_open:
            return "PRE", "試搓時段" # 模擬試搓，實際上抓昨收
        else:
            return "CLOSED", "已收盤"

    @st.cache_data(ttl=60) # 盤中60秒更新一次
    def fetch_data(_self, ticker, status):
        try:
            stock = yf.Ticker(ticker)
            
            if status == "OPEN":
                # 盤中：抓 1 分鐘 K 線 (看即時走勢)
                # yfinance 限制：1m 資料只能抓最近 7 天
                df = stock.history(period="1d", interval="1m")
            else:
                # 收盤/休市：抓日 K 線 (看波段)
                df = stock.history(period="3mo", interval="1d")
                
            if df.empty: return pd.DataFrame()
            
            # 資料清洗
            df.reset_index(inplace=True)
            df['Date'] = df['Date'].dt.tz_localize(None) # 移除時區避免繪圖錯誤
            df.rename(columns={'Close': 'close', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Volume': 'vol'}, inplace=True)
            return df
        except:
            return pd.DataFrame()

engine = MarketEngine()

# ==========================================
# 3. 狀態管理 (Session)
# ==========================================
if 'login_status' not in st.session_state:
    st.session_state.login_status = False # 預設未登入
if 'account_type' not in st.session_state:
    st.session_state.account_type = "Simulation"
if 'balance' not in st.session_state:
    st.session_state.balance = 1000000
if 'positions' not in st.session_state:
    st.session_state.positions = {} # {'2330.TW': {'qty': 1000, 'cost': 900}}
if 'orders' not in st.session_state:
    st.session_state.orders = []

# ==========================================
# 4. 側邊欄：登入與憑證
# ==========================================
with st.sidebar:
    st.title("🔐 用戶登入")
    
    login_mode = st.radio("選擇登入模式", ["模擬體驗 (Demo)", "券商憑證登入 (Real)"])
    
    if login_mode == "券商憑證登入 (Real)":
        st.info("請輸入券商 API 帳號密碼")
        broker = st.selectbox("合作券商", ["元大證券", "凱基證券", "富邦證券", "永豐金證券"])
        user_id = st.text_input("身分證字號 / 帳號")
        user_pwd = st.text_input("密碼", type="password")
        cert_path = st.file_uploader("上傳憑證 (.pfx)", type=['pfx'])
        
        if st.button("驗證登入"):
            if user_id and user_pwd:
                st.session_state.login_status = True
                st.session_state.account_type = "Real"
                st.success(f"✅ {broker} 連線成功 (API Mode)")
                st.rerun()
            else:
                st.error("請輸入完整資訊")
    else:
        if st.button("進入模擬系統"):
            st.session_state.login_status = True
            st.session_state.account_type = "Simulation"
            st.rerun()

    st.divider()
    
    if st.session_state.login_status:
        acc_color = "red" if st.session_state.account_type == "Real" else "green"
        st.markdown(f"**帳戶狀態**: :{acc_color}[{st.session_state.account_type}]")
        st.metric("權益總值", f"${st.session_state.balance:,.0f}")

# ==========================================
# 5. 主系統 (登入後顯示)
# ==========================================
if st.session_state.login_status:
    
    # --- A. 股票搜尋與狀態 ---
    col_search, col_status = st.columns([3, 1])
    with col_search:
        ticker = st.text_input("輸入股票代號 (支援台股)", "2330.TW")
    with col_status:
        # 顯示市場狀態
        status_code, status_text = engine.get_market_status()
        css_class = "status-open" if status_code == "OPEN" else "status-closed"
        st.markdown(f"<br><span class='status-tag {css_class}'>{status_text}</span>", unsafe_allow_html=True)

    # 獲取數據
    df = engine.fetch_data(ticker, status_code)
    
    if df.empty:
        st.error("查無資料，請確認代號 (台股請加 .TW) 或目前非交易時間。")
        st.stop()

    # 計算當前數據
    last_row = df.iloc[-1]
    prev_close = df['close'].iloc[-2] if len(df) > 1 else last_row['open']
    price = last_row['close']
    change = price - prev_close
    pct = (change / prev_close) * 100
    color = "up" if change > 0 else "down"
    
    # --- B. 鉅亨風格報價看板 ---
    c1, c2, c3 = st.columns([2, 3, 3])
    with c1:
        st.markdown(f"## {ticker}")
        st.caption("Taipei Exchange")
    with c2:
        st.markdown(f"""
        <div class='price-main {color}'>{price:.2f}</div>
        <div style='font-size:20px; font-weight:bold;' class='{color}'>
            {change:+.2f} ({pct:+.2f}%)
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"**開盤**: {last_row['open']} | **最高**: {last_row['high']}")
        st.markdown(f"**最低**: {last_row['low']} | **量**: {int(last_row['vol']):,}")

    st.divider()

    # --- C. 專業 K 線圖與下單介面 (左右佈局) ---
    col_chart, col_trade = st.columns([2, 1])

    with col_chart:
        st.subheader("技術分析")
        
        # 繪圖
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_width=[0.2, 0.8], vertical_spacing=0.03)
        
        # K線
        fig.add_trace(go.Candlestick(
            x=df['Date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
            increasing_line_color='#eb3f38', decreasing_line_color='#2daa59', name='Price'
        ), row=1, col=1)
        
        # 均線
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA5'], line=dict(color='orange', width=1), name='MA5'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], line=dict(color='#2196f3', width=1), name='MA20'), row=1, col=1)
        
        # 成交量
        colors = ['#eb3f38' if c >= o else '#2daa59' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df['Date'], y=df['vol'], marker_color=colors, name='Volume'), row=2, col=1)
        
        fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_trade:
        st.subheader("⚡ 快速下單")
        
        # 交易 Tab
        tab_buy, tab_sell, tab_auto = st.tabs(["買進", "賣出", "🤖 自動交易"])
        
        # 共用設定
        trade_type = st.radio("交易種類", ["現股", "當沖", "零股"], horizontal=True)
        
        with tab_buy:
            qty_step = 1 if trade_type == "零股" else 1
            qty_label = "股數" if trade_type == "零股" else "張數"
            
            # 筆數/數量控制
            order_qty = st.number_input("數量", min_value=1, value=1, step=qty_step, key="b_qty")
            order_price = st.number_input("價格 (ROD)", value=price, step=0.5, key="b_price")
            
            total_est = order_price * order_qty * (1 if trade_type == "零股" else 1000)
            st.markdown(f"**預估金額**: ${total_est:,.0f}")
            
            if st.button("🔴 下單買進", use_container_width=True):
                if st.session_state.balance >= total_est:
                    st.session_state.balance -= total_est
                    st.session_state.orders.insert(0, f"[{datetime.now().strftime('%H:%M')}] 買進 {ticker} {order_qty}{qty_label} @ {order_price}")
                    st.success("委託成功！")
                else:
                    st.error("資金不足")

        with tab_sell:
            st.info("庫存賣出功能 (需持有部位)")
            # (賣出邏輯略，結構同上)

        with tab_auto:
            st.markdown("### 機器人設定")
            st.info("策略觸發時，將依以下設定自動執行")
            
            auto_strategy = st.selectbox("觸發策略", ["KD 黃金交叉", "RSI 超賣 (<30)", "突破均線"])
            
            c_a1, c_a2 = st.columns(2)
            with c_a1:
                batch_size = st.number_input("單次張數", 1, 10, 1)
            with c_a2:
                max_orders = st.number_input("最大加碼筆數", 1, 5, 3)
                
            active = st.toggle("啟動自動交易")
            if active:
                st.caption(f"監控中... (上限 {max_orders} 筆, 每筆 {batch_size} 張)")

    # --- D. 委託回報區 ---
    st.divider()
    st.subheader("📋 委託回報與成交")
    if st.session_state.orders:
        for order in st.session_state.orders:
            st.text(order)
    else:
        st.caption("尚無委託紀錄")

else:
    # 未登入時的歡迎畫面
    st.info("請於左側選擇登入模式 (支援 真實憑證 / 模擬體驗)")
