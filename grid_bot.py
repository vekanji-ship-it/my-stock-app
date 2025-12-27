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
# 1. 系統初始化 & CSS 風格 (與 app.py 一致)
# ==========================================
st.set_page_config(page_title="股市特務 X - 網格戰神版", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    /* 全局風格 - 淺色系 */
    .stApp { background-color: #f4f7f6; font-family: 'Microsoft JhengHei', 'PingFang TC', sans-serif; }
    
    /* 導航條 */
    .nav-bar { 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px; color: white;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .nav-title { font-size: 26px; font-weight: bold; letter-spacing: 1px; }
    
    /* 通用卡片容器 */
    .card { 
        background: white; padding: 15px; border-radius: 10px; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 10px; 
    }
    
    /* 網格交易表格樣式 */
    .grid-row {
        padding: 12px; border-bottom: 1px solid #eee;
        display: flex; justify-content: space-between; align-items: center;
        transition: 0.2s;
    }
    .grid-row:hover { background-color: #f8f9fa; }
    .grid-active {
        background: #e3f2fd; border-left: 5px solid #2196f3;
        font-weight: bold;
    }
    
    /* 股票標頭 */
    .stock-header { background: white; padding: 20px; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .stock-price-lg { font-size: 36px; font-weight: bold; }
    .stock-meta { color: #666; font-size: 14px; }
    .up { color: #d32f2f; } .down { color: #2e7d32; }
    
    /* 隱藏預設元件 */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎 (整合版)
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        # 內建台股名稱翻譯字典
        self.name_map = {
            "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2603": "長榮", "0050": "元大台灣50",
            "0056": "元大高股息", "00878": "國泰永續高股息", "00632R": "元大台灣50反1"
        }

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
            
            display_name = _self.get_stock_name(ticker.replace('.TW', ''))
            return {
                "name": display_name, "price": price, "change": change,
                "pct": pct, "vol": last.get('Volume', 0), 
                "open": last['Open'], "high": last['High'], "low": last['Low']
            }
        except: return None

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

# 繪圖函數 (支援淺色風格)
def plot_chart(df, title, levels=None, current_price=None):
    # 判斷時間欄位
    x_col = 'datetime' if 'datetime' in df.columns else 'date'
    
    fig = go.Figure(data=[go.Candlestick(
        x=df[x_col], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='K線',
        increasing_line_color='#d32f2f', decreasing_line_color='#2e7d32'
    )])
    
    # 繪製網格線
    if levels:
        upper = max(levels)
        lower = min(levels)
        for p in levels:
            color = "rgba(100, 100, 100, 0.3)"
            width = 1
            dash = "dot"
            if abs(p - upper) < 0.01: color, width, dash = "rgba(255, 0, 0, 0.5)", 2, "solid" # 紅色天花板
            if abs(p - lower) < 0.01: color, width, dash = "rgba(0, 128, 0, 0.5)", 2, "solid" # 綠色地板
            fig.add_hline(y=p, line_dash=dash, line_color=color, line_width=width)

    # 繪製現價線
    if current_price:
        fig.add_hline(y=current_price, line_color="#2196f3", line_width=1.5, annotation_text="現價")

    fig.update_layout(
        title=title, height=450, 
        xaxis_rangeslider_visible=False, 
        margin=dict(l=10, r=10, t=30, b=10), 
        yaxis_title="價格", 
        hovermode="x unified",
        paper_bgcolor='white', # 淺色背景
        plot_bgcolor='white',
        font=dict(color="black")
    )
    fig.update_xaxes(showgrid=True, gridcolor='#eee')
    fig.update_yaxes(showgrid=True, gridcolor='#eee')
    return fig

# ==========================================
# 3. 模組一：股市情報站 (Dashboard) - 維持原樣
# ==========================================
def render_dashboard():
    st.markdown("<div class='nav-bar'><span class='nav-title'>📊 股市情報站 (Dashboard)</span></div>", unsafe_allow_html=True)
    
    col_main, col_news = st.columns([3, 2])
    
    with col_main:
        st.subheader("🔎 全方位個股偵查")
        ticker = st.text_input("輸入代號 (例如 2330)", "2330", key="dash_input")
        
        q = engine.fetch_quote(ticker)
        
        if q:
            color_cls = "up" if q['change'] > 0 else "down"
            st.markdown(f"""
            <div class='stock-header'>
                <span class='stock-price-lg {color_cls}'>{q['price']}</span>
                <span class='stock-meta {color_cls}' style='margin-left:10px; font-size:20px;'>{q['change']:+.2f} ({q['pct']:+.2f}%)</span>
                <div class='stock-meta'>代號: {ticker} | 名稱: {q['name']} | 成交量: {q['vol']:,}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # === K 線圖表 ===
            c_k_opt, c_k_void = st.columns([1, 4])
            k_type = c_k_opt.radio("K線週期", ["日K", "週K", "月K"], horizontal=True, label_visibility="collapsed")
            
            if k_type == "日K": k_inv, k_prd = "1d", "3mo"
            elif k_type == "週K": k_inv, k_prd = "1wk", "1y"
            else: k_inv, k_prd = "1mo", "5y"
            
            df_k = engine.fetch_kline(ticker, interval=k_inv, period=k_prd)
            
            if not df_k.empty:
                st.plotly_chart(plot_chart(df_k, f"{q['name']} ({ticker}) - {k_type}線圖"), use_container_width=True)
            else:
                st.warning("查無此週期 K 線資料")

    with col_news:
        st.subheader("📰 市場頭條")
        news_list = engine.get_real_news()
        for news in news_list:
            st.markdown(f"""
            <div style='padding:10px; border-bottom:1px solid #eee; background:white; border-radius:5px; margin-bottom:8px;'>
                <a href='{news['link']}' target='_blank' style='text-decoration:none; color:#333; font-weight:bold;'>{news['title']}</a>
                <div style='font-size:12px; color:#888;'>{news['time']} | {news['source']}</div>
            </div>
            """, unsafe_allow_html=True)

# ==========================================
# 4. 模組二：網格戰神 (Grid Bot) - 新版邏輯 + 舊版風格
# ==========================================
def calculate_grid(upper, lower, grids, investment):
    if upper <= lower: return [], 0, 0
    diff = upper - lower
    step = diff / grids
    cash_per_grid = investment / grids
    levels = [lower + (i * step) for i in range(grids + 1)]
    return sorted(levels, reverse=True), step, cash_per_grid

def render_grid_bot():
    st.markdown("<div class='nav-bar'><span class='nav-title'>⚡ 網格戰神 (Grid Master)</span></div>", unsafe_allow_html=True)
    
    # === 1. 設定區域 (放在上方卡片) ===
    with st.expander("🔧 策略參數設定 (點擊展開/收合)", expanded=True):
        col_input_1, col_input_2 = st.columns([1, 2])
        
        with col_input_1:
            st.markdown("#### 1. 標的選擇")
            ticker = st.text_input("交易代號", "00632R", help="網格適合震盪標的")
            q = engine.fetch_quote(ticker)
            cur_price = q['price'] if q else 10.0
            
            if q:
                st.success(f"✅ {q['name']} 現價: {cur_price}")
            else:
                st.error("❌ 查無報價")
        
        with col_input_2:
            st.markdown("#### 2. 網格參數")
            c1, c2, c3, c4 = st.columns(4)
            upper_price = c1.number_input("上限 (天花板)", value=float(cur_price * 1.05), format="%.2f")
            lower_price = c2.number_input("下限 (地板)", value=float(cur_price * 0.95), format="%.2f")
            grid_num = c3.number_input("格數", value=10, min_value=2, step=1)
            invest_amt = c4.number_input("投入金額", value=100000, step=10000)

    # === 計算邏輯 ===
    levels, step, cash_per_grid = calculate_grid(upper_price, lower_price, grid_num, invest_amt)

    # === 2. 主畫面 (圖表 + 表格) ===
    col_chart, col_list = st.columns([2, 1])
    
    with col_chart:
        st.subheader("📉 網格區間可視化")
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        
        # 繪圖
        df_grid = engine.fetch_kline(ticker, interval="60m", period="1mo") # 網格用60分K看
        if not df_grid.empty:
            profit_pct = (step / lower_price) * 100 if lower_price > 0 else 0
            st.plotly_chart(plot_chart(df_grid, f"預期單格利潤: {profit_pct:.2f}% | 間距: {step:.2f}", levels, cur_price), use_container_width=True)
        else:
            st.warning("等待數據加載...")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_list:
        st.subheader("📋 交易指令表")
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        
        # 統計資訊
        st.markdown(f"""
        <div style='display:flex; justify-content:space-between; margin-bottom:10px;'>
            <div><b>每格資金:</b> ${cash_per_grid:,.0f}</div>
            <div><b>總格數:</b> {grid_num} 格</div>
        </div>
        <hr style='margin:5px 0;'>
        """, unsafe_allow_html=True)
        
        # 產生指令表
        if levels:
            # 找現價區間
            curr_zone_idx = -1
            for i in range(len(levels)-1):
                if levels[i] >= cur_price >= levels[i+1]:
                    curr_zone_idx = i
                    break
            
            # 顯示表格 (可滾動)
            scroll_container = st.container(height=400)
            with scroll_container:
                for i, p in enumerate(levels):
                    action_html = "<span style='color:#ccc'>觀望</span>"
                    row_cls = "grid-row"
                    
                    if p > cur_price:
                        action_html = "<span style='color:#d32f2f; font-weight:bold;'>待賣出 Sell</span>"
                    elif p < cur_price:
                        action_html = "<span style='color:#2e7d32; font-weight:bold;'>待買入 Buy</span>"
                    
                    # 高亮目前區間
                    if i == curr_zone_idx or i == curr_zone_idx + 1:
                        row_cls += " grid-active"
                        action_html += " 📍"

                    st.markdown(f"""
                    <div class='{row_cls}'>
                        <span style='font-family:monospace; font-size:16px;'>{p:.2f}</span>
                        {action_html}
                    </div>
                    """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 5. 主程式導航
# ==========================================
with st.sidebar:
    st.title("🕵️ 股市特務 X")
    st.markdown("---")
    module = st.radio("功能導航", ["📊 股市情報站", "⚡ 網格戰神"])
    st.markdown("---")
    st.info("網格戰神：專為震盪盤設計，自動計算買低賣高區間。")
    if st.button("清除快取"):
        st.cache_data.clear()
        st.rerun()

if module == "📊 股市情報站":
    render_dashboard()
elif module == "⚡ 網格戰神":
    render_grid_bot()
