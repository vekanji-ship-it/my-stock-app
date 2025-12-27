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
# 1. 系統初始化 & CSS 風格
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
    
    /* 漲跌色 */
    .up { color: #d32f2f; font-weight: bold; } 
    .down { color: #2e7d32; font-weight: bold; }
    
    /* 新聞列表 */
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
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 核心數據引擎
# ==========================================
class DataEngine:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Taipei')
        self.watch_list = [
            "2330", "2317", "2454", "2603", "2609", "2615", "3231", "2382", "2356", "2303", 
            "2881", "2882", "2891", "2376", "2388", "3037", "3035", "3017", "2368", "3008",
            "1513", "1519", "1503", "1504", "2515", "2501", "2002", "1605", "2344", "2409"
        ]

    def is_market_open(self):
        now = datetime.now(self.tz)
        if now.weekday() >= 5: return False
        return dt_time(9, 0) <= now.time() <= dt_time(13, 30)

    @st.cache_data(ttl=60)
    def fetch_quote(_self, ticker):
        if not ticker.endswith('.TW') and not ticker.startswith('^'): ticker += '.TW'
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
                
            try: name = stock.info.get('longName', ticker)
            except: name = ticker
            
            return {
                "name": name, "price": price, "change": change,
                "pct": pct, "vol": last['Volume'], 
                "open": last['Open'], "high": last['High'], "low": last['Low']
            }
        except: return None
        
    @st.cache_data(ttl=3600) # 基本資料快取久一點
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
                data_list.append({
                    "代號": code, "股價": price, "漲跌幅": change_pct, "成交量": vol,
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
if 'login_status' not in st.session_state: st.session_state.login_status = False
if 'member_tier' not in st.session_state: st.session_state.member_tier = "一般會員"
if 'line_token' not in st.session_state: st.session_state.line_token = ""
if 'line_uid' not
