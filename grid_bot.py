import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, time as dt_time
import pytz

# ==========================================
# 1. 系統設定 (深色模式)
# ==========================================
st.set_page_config(page_title="網格戰神 (Grid Master)", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    /* 強制深色背景風格 */
    .stApp { background-color: #121212; color: #e0e0e0; }
    
    /* 網格表格樣式 */
    .grid-row {
        padding: 10px; border-radius: 5px; margin-bottom: 5px;
        display: flex; justify-content: space-between; align-items: center;
        border: 1px solid #444; background: #2b2b2b;
    }
    .grid-active {
        background: #1e3a5f; border: 2px solid #2196f3;
        box-shadow: 0 0 10px rgba(33, 150, 243, 0.3);
    }
    
    /* 統計卡片 */
    .stat-card {
        background: #1e1e1e; padding: 15px; border-radius: 8px; border: 1px solid #333;
        text-align: center;
    }
    .stat-val { font-size: 24px; font-weight: bold; color: #fff; }
    .stat-lbl { font-size: 14px; color: #aaa; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 簡化版數據引擎
# ==========================================
class SimpleEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
    
    def fetch_price(self, ticker):
        # 自動補全台股代號
        if not ticker.endswith('.TW') and not ticker.startswith('^') and ticker.isdigit(): 
            ticker += '.TW'
            
        try:
            stock = yf.Ticker(ticker)
            # 抓取最新數據
            df = stock.history(period='1d', interval='1m')
            if df.empty: 
                df = stock.history(period='5d', interval='1d')
            
            if df.empty: return ticker, None
            
            price = float(df.iloc[-1]['Close'])
            name = ticker.replace('.TW', '') 
            return name, price
        except: return ticker, None

    def get_history(self, ticker):
        if not ticker.endswith('.TW') and not ticker.startswith('^') and ticker.isdigit(): 
            ticker += '.TW'
        try:
            stock = yf.Ticker(ticker)
            return stock.history(period='1mo', interval='60m') # 網格觀察 60分K
        except: return pd.DataFrame()

engine = SimpleEngine()

# ==========================================
# 3. 網格邏輯核心
# ==========================================
def calculate_grid(upper, lower, grids, investment):
    if upper <= lower: return None, 0, 0
    
    diff = upper - lower
    step = diff / grids
    cash_per_grid = investment / grids
    
    levels = []
    # 產生網格價格表 (從高到低排序)
    for i in range(grids + 1):
        price = lower + (i * step)
        levels.append(price)
    
    return sorted(levels, reverse=True), step, cash_per_grid

# ==========================================
# 4. 介面層
# ==========================================
st.title("⚡ 網格戰神 (Grid Master)")
st.caption("專為震盪盤整設計的自動化交易策略計算機")

# --- 側邊欄：設定參數 ---
st.sidebar.header("🔧 策略參數設定")
ticker_input = st.sidebar.text_input("交易代號", "0050") 
st.sidebar.caption("支援台股 (2330)、美股 (AAPL)、外匯 (JPY=X)")

name, current_price = engine.fetch_price(ticker_input)

if current_price:
    st.sidebar.success(f"✅ {name} 現價: {current_price}")
else:
    st.sidebar.error("❌ 無法抓取報價，請檢查代號")
    current_price = 100.0 # Fallback 避免報錯

st.sidebar.divider()
# 網格設定
upper_price = st.sidebar.number_input("天花板價格 (上限)", value=float(current_price * 1.1))
lower_price = st.sidebar.number_input("地板價格 (下限)", value=float(current_price * 0.9))
grid_num = st.sidebar.number_input("網格格數", value=10, min_value=2, step=1)
invest_amt = st.sidebar.number_input("總投入資金", value=100000, step=10000)

if st.sidebar.button("🔄 重新計算"):
    st.rerun()

# --- 主畫面 ---
col_chart, col_table = st.columns([2, 1])

levels, step, cash_per_grid = calculate_grid(upper_price, lower_price, grid_num, invest_amt)

with col_chart:
    st.subheader(f"📉 {name} 區間可視化")
    
    # 繪製 K 線圖 + 網格線
    df = engine.get_history(ticker_input)
    if not df.empty:
        df.reset_index(inplace=True)
        # 處理時區問題
        if df['Datetime'].dt.tz is not None:
            df['Datetime'] = df['Datetime'].dt.tz_localize(None) 
        
        fig = go.Figure(data=[go.Candlestick(
            x=df['Datetime'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name='股價'
        )])
        
        # 畫出所有網格線
        if levels:
            for p in levels:
                color = "gray"
                width = 1
                dash = "dot"
                if abs(p - upper_price) < 0.01: color, width, dash = "#ff5252", 2, "solid" # 紅色天花板
                if abs(p - lower_price) < 0.01: color, width, dash = "#69f0ae", 2, "solid" # 綠色地板
                
                fig.add_hline(y=p, line_dash=dash, line_color=color, line_width=width)

        # 標記現價
        fig.add_hline(y=current_price, line_color="#2196f3", line_width=2, annotation_text="現價")
        
        profit_pct = (step / lower_price) * 100 if lower_price > 0 else 0
        fig.update_layout(
            height=600, 
            template="plotly_dark", 
            title=f"網格間距: {step:.2f} | 預期單格利潤: {profit_pct:.2f}%",
            xaxis_rangeslider_visible=False,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("無歷史數據可供繪圖")

with col_table:
    st.subheader("📋 交易指令表")
    
    # 統計卡片
    c1, c2 = st.columns(2)
    c1.markdown(f"<div class='stat-card'><div class='stat-val'>${cash_per_grid:,.0f}</div><div class='stat-lbl'>每格資金</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-card'><div class='stat-val'>{step:.2f}</div><div class='stat-lbl'>網格間距</div></div>", unsafe_allow_html=True)
    
    st.write("---")
    
    if levels:
        # 找到目前價格所在的區間索引
        curr_zone_idx = -1
        for i in range(len(levels)-1):
            if levels[i] >= current_price >= levels[i+1]:
                curr_zone_idx = i
                break
        
        # 產生表格
        st.write("目前價格位置與操作建議：")
        
        container = st.container(height=500) # 讓表格可以捲動
        with container:
            for i, p in enumerate(levels):
                status_color = "#aaa"
                action_text = ""
                action_style = ""
                row_class = "grid-row"
                
                if p > current_price:
                    status_color = "#ff5252" # 紅
                    action_text = "待賣出 (Sell)"
                    action_style = "color: #ff5252; font-weight: bold;"
                elif p < current_price:
                    status_color = "#69f0ae" # 綠
                    action_text = "待買入 (Buy)"
                    action_style = "color: #69f0ae; font-weight: bold;"
                else:
                    action_text = "觀望"
                
                # 高亮目前區間 (現價上下兩格)
                if i == curr_zone_idx or i == curr_zone_idx + 1:
                    row_class += " grid-active"
                
                html = f"""
                <div class='{row_class}'>
                    <span style='font-size: 16px; font-weight: bold; color: {status_color};'>{p:.2f}</span>
                    <span style='font-size: 14px; {action_style}'>{action_text}</span>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)
