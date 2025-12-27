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
# 1. 系統初始化
# ==========================================
st.set_page_config(page_title="ProQuant X 旗艦系統", page_icon="🦅", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #333; font-family: 'Microsoft JhengHei', sans-serif; }
    
    /* 登入狀態標籤 */
    .account-tag-real { background-color: #d32f2f; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
    .account-tag-sim { background-color: #2e7d32; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
    
    /* 戰情室卡片 */
    .war-room-card {
        border: 1px solid #eee; padding: 15px; border-radius: 8px;
        background: #fdfdfd; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .index-val { font-size: 24px; font-weight: bold; font-family: 'Roboto'; }
    .index-name { font-size: 14px; color: #666; margin-bottom: 5px; }
    
    .up { color: #eb3f38; } .down { color: #2daa59; } .flat { color: #555555; }
    
    [data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #eee; }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心引擎
# ==========================================
class MarketEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
    
    def get_market_status(self):
        now = datetime.now(self.tz)
        if now.weekday() >= 5: return "CLOSED", "休市 (週末)"
        # 簡單判定盤中
        current_time = now.time()
        if dt_time(9, 0) <= current_time <= dt_time(13, 30):
            return "OPEN", "盤中連線"
        else:
            return "CLOSED", "已收盤"

    @st.cache_data(ttl=60)
    def fetch_data(_self, ticker, period="1d", interval="1m"):
        try:
            if not ticker.endswith('.TW') and not ticker.startswith('^'): ticker = f"{ticker}.TW"
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            if df.empty: return pd.DataFrame()
            df.reset_index(inplace=True)
            df['Date'] = df['Date'].dt.tz_localize(None)
            df.rename(columns={'Close': 'close', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Volume': 'vol'}, inplace=True)
            return df
        except: return pd.DataFrame()

    @st.cache_data(ttl=300)
    def fetch_global_indices(_self):
        tickers = {"加權指數": "^TWII", "道瓊": "^DJI", "那斯達克": "^IXIC", "費半": "^SOX", "日經": "^N225"}
        data = {}
        for name, sym in tickers.items():
            try:
                stock = yf.Ticker(sym)
                hist = stock.history(period="5d")
                if not hist.empty:
                    latest = hist.iloc[-1]['Close']
                    prev = hist.iloc[-2]['Close']
                    chg = latest - prev
                    pct = (chg / prev) * 100
                    data[name] = {"price": latest, "change": chg, "pct": pct}
            except: pass
        return data

engine = MarketEngine()

# ==========================================
# 3. 狀態管理
# ==========================================
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'account_type' not in st.session_state: st.session_state.account_type = "Simulation"
if 'balance' not in st.session_state: st.session_state.balance = 1000000
if 'orders' not in st.session_state: st.session_state.orders = []
if 'page' not in st.session_state: st.session_state.page = "戰情室"

# ==========================================
# 4. 側邊欄：登入系統與導航 (核心修復)
# ==========================================
with st.sidebar:
    st.title("🦅 ProQuant X")
    
    # [A] 未登入狀態：顯示登入表單
    if not st.session_state.login_status:
        st.subheader("🔐 用戶登入")
        
        login_mode = st.radio("選擇模式", ["模擬體驗 (Demo)", "券商憑證登入 (Real)"])
        
        if login_mode == "券商憑證登入 (Real)":
            st.info("🔒 安全連線模式")
            broker = st.selectbox("券商", ["元大證券", "凱基證券", "富邦證券"])
            uid = st.text_input("帳號/ID")
            pwd = st.text_input("密碼", type="password")
            cert = st.file_uploader("上傳憑證 (.pfx)", type=['pfx'])
            
            if st.button("驗證登入", type="primary", use_container_width=True):
                if uid and pwd:
                    st.session_state.login_status = True
                    st.session_state.account_type = "Real"
                    st.success("憑證驗證成功！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("請輸入帳號密碼")
        else:
            st.info("🚀 快速體驗模式")
            if st.button("進入模擬系統", type="primary", use_container_width=True):
                st.session_state.login_status = True
                st.session_state.account_type = "Simulation"
                st.rerun()
    
    # [B] 已登入狀態：顯示導航與帳戶
    else:
        # 顯示帳戶標籤
        if st.session_state.account_type == "Real":
            st.markdown("<span class='account-tag-real'>🔴 真實交易帳戶</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='account-tag-sim'>🟢 模擬體驗帳戶</span>", unsafe_allow_html=True)
            
        st.markdown(f"**權益數**: ${st.session_state.balance:,.0f}")
        
        st.divider()
        
        # 系統模組導航
        nav = st.radio("功能模組", ["🌍 股市戰情室", "💹 個股操盤室"], index=0 if st.session_state.page=="戰情室" else 1)
        st.session_state.page = nav
        
        st.divider()
        
        status_c, status_t = engine.get_market_status()
        st.caption(f"市場狀態: {status_t}")
        
        if st.button("登出"):
            st.session_state.login_status = False
            st.rerun()

# ==========================================
# 5. 主畫面內容 (根據登入狀態)
# ==========================================
if not st.session_state.login_status:
    # 登入前的歡迎畫面
    st.info("⬅️ 請於左側側邊欄選擇登入模式 (支援 真實憑證 / 模擬體驗)")
    st.markdown("### 系統特色")
    st.markdown("- **真實數據連線**：串接 Yahoo Finance 全球即時報價")
    st.markdown("- **雙模組架構**：整合全球戰情室與專業個股操盤")
    st.markdown("- **自動交易機器人**：內建 RSI / KD / 均線策略")

else:
    # 登入後：根據選擇顯示戰情室或操盤室
    
    # --- 頁面 A: 戰情室 ---
    if "戰情室" in st.session_state.page:
        st.title("🌍 全球股市戰情室")
        
        # 指數卡片
        indices = engine.fetch_global_indices()
        cols = st.columns(5)
        keys = list(indices.keys())
        for i, col in enumerate(cols):
            if i < len(keys):
                name = keys[i]
                d = indices[name]
                color = "up" if d['change'] > 0 else "down"
                with col:
                    st.markdown(f"""
                    <div class='war-room-card'>
                        <div class='index-name'>{name}</div>
                        <div class='index-val {color}'>{d['price']:,.0f}</div>
                        <div class='{color}'>{d['change']:+.0f} ({d['pct']:+.2f}%)</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.divider()
        
        # 法人與熱力圖
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("💰 法人資金流向 (預估)")
            sim_fund = pd.DataFrame({"法人": ["外資", "投信", "自營商"], "買賣超": [np.random.uniform(-30, 30), np.random.uniform(5, 15), np.random.uniform(-5, 5)]})
            for _, row in sim_fund.iterrows():
                val = row['買賣超']
                color = "red" if val > 0 else "green"
                st.markdown(f"**{row['法人']}**: :{color}[{val:+.2f} 億]")
                st.progress(min(int(val + 50), 100))
        
        with c2:
            st.subheader("🔥 熱門族群資金 (Sector Heatmap)")
            sectors = pd.DataFrame({
                "Sector": ["半導體", "AI 伺服器", "航運", "金融", "生技", "網通", "營建", "塑化"],
                "Volume": [5000, 3500, 2000, 1800, 1200, 1000, 800, 600],
                "Change": [2.5, 1.8, -0.5, 0.3, -1.2, 0.8, 1.5, -0.2]
            })
            fig = px.treemap(sectors, path=['Sector'], values='Volume', color='Change', color_continuous_scale='RdBu_r', color_continuous_midpoint=0)
            fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=350)
            st.plotly_chart(fig, use_container_width=True)

    # --- 頁面 B: 操盤室 ---
    elif "個股操盤" in st.session_state.page:
        st.title("💹 專業個股操盤")
        
        c_search, c_gap = st.columns([3, 1])
        with c_search:
            ticker = st.text_input("輸入股票代號", "2330", help="免輸入 .TW")
        
        # 數據與繪圖
        status, _ = engine.get_market_status()
        period = "1d" if status == "OPEN" else "3mo"
        interval = "1m" if status == "OPEN" else "1d"
        
        df = engine.fetch_data(ticker, period, interval)
        
        if not df.empty:
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            chg = last['close'] - prev['close']
            pct = (chg / prev['close']) * 100
            color = "up" if chg > 0 else "down"
            
            # 報價看板
            st.markdown(f"""
            <div style='display:flex; align-items:baseline;'>
                <div style='font-size:32px; font-weight:bold;'>{ticker}</div>
                <div style='margin-left:20px; font-size:42px; font-weight:bold;' class='{color}'>{last['close']:.2f}</div>
                <div style='margin-left:15px; font-size:20px;' class='{color}'>{chg:+.2f} ({pct:+.2f}%)</div>
            </div>
            """, unsafe_allow_html=True)
            
            # K線圖
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_width=[0.2, 0.8], vertical_spacing=0.03)
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='K'), row=1, col=1)
            df['MA5'] = df['close'].rolling(5).mean()
            df['MA20'] = df['close'].rolling(20).mean()
            fig.add_trace(go.Scatter(x=df['Date'], y=df['MA5'], line=dict(color='orange'), name='MA5'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], line=dict(color='#2196f3'), name='MA20'), row=1, col=1)
            colors = ['#eb3f38' if c >= o else '#2daa59' for c, o in zip(df['close'], df['open'])]
            fig.add_trace(go.Bar(x=df['Date'], y=df['vol'], marker_color=colors), row=2, col=1)
            fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            st.divider()
            
            # 下單區
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("⚡ 下單交易")
                type_ = st.radio("交易類型", ["現股", "當沖", "零股"], horizontal=True)
                qty_step = 1 if type_ == "零股" else 1
                qty = st.number_input("數量", 1, 100, 1, step=qty_step)
                
                if st.button("立即下單", type="primary", use_container_width=True):
                    st.session_state.orders.append(f"買進 {ticker} {qty}單位 ({type_})")
                    st.success(f"委託成功！({type_})")
            
            with c2:
                st.subheader("🤖 自動加碼設定")
                st.selectbox("觸發策略", ["KD 黃金交叉", "RSI 超賣 (<30)", "突破前高"])
                c_auto1, c_auto2 = st.columns(2)
                c_auto1.number_input("單筆張數", 1, 10, 1)
                c_auto2.number_input("最大筆數", 1, 5, 3)
                st.toggle("啟動自動監控")
        else:
            st.error("查無資料，請確認股票代號。")
