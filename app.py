import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import os
import plotly.graph_objects as go
from datetime import datetime

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="🇺🇸 トレンドトラッカー v6.0", layout="wide")
st.title("🇺🇸 トレンドトラッカー v6.0 🚀")

try:
    AV_API_KEY = st.secrets.get("AV_API_KEY", "")
except Exception:
    AV_API_KEY = ""

CACHE_FILE = "financial_data_cache.csv"

# --- 2. 共通関数（CSV読み込み強化） ---
@st.cache_data
def load_themes_from_csv():
    csv_path = 'themes.csv'
    if not os.path.exists(csv_path):
        st.error(f"⚠️ {csv_path} が見つかりません。")
        return {}, []
    try:
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
        if 'テーマ' not in df.columns or 'ティッカー' not in df.columns:
            if len(df.columns) >= 2: df.columns = ['テーマ', 'ティッカー'] + list(df.columns[2:])
            else: return {}, []
        df['テーマ'] = df['テーマ'].astype(str).str.strip()
        df['ティッカー'] = df['ティッカー'].astype(str).str.strip().str.upper()
        return df.groupby('テーマ')['ティッカー'].apply(list).to_dict(), df['ティッカー'].unique().tolist()
    except Exception: return {}, []

themes, all_tickers = load_themes_from_csv()

# --- 3. キャッシュ管理と一括取得ロジック ---
def load_git_cache():
    if os.path.exists(CACHE_FILE):
        try: return pd.read_csv(CACHE_FILE, index_col=0).to_dict('index')
        except: return {}
    return {}

def save_git_cache(data_dict):
    try:
        df = pd.DataFrame.from_dict(data_dict, orient='index')
        df.to_csv(CACHE_FILE)
        return True
    except: return False

def get_comprehensive_info(t, api_key, force_update=False):
    p_cache = load_git_cache()
    if not force_update and t in p_cache:
        data = p_cache[t]
        data["source"] = "Git Cache (CSV)"
        return data

    data = {"ticker": t, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
    try:
        session = yf.Ticker(t)
        info = session.info
        if info and len(info) > 10:
            data.update({
                "shares": info.get("sharesOutstanding"), "eps": info.get("trailingEps"),
                "f_eps": info.get("forwardEps"), "margin": info.get("operatingMargins"),
                "ebitda": info.get("ebitda"), "roe": info.get("returnOnEquity"),
                "rev_growth": info.get("revenueGrowth"), "earn_growth": info.get("earningsGrowth"),
                "mcap_raw": info.get("marketCap"), "t_mean": info.get("targetMeanPrice"),
                "t_high": info.get("targetHighPrice"), "t_low": info.get("targetLowPrice"),
                "rec": info.get("recommendationKey"), "source": "Yahoo API"
            })
            p_cache[t] = data
            save_git_cache(p_cache)
    except: pass
    return data

# --- 4. メイン表示部 ---
# サイドバーに一括取得ボタンを配置（Ubuntu用）
with st.sidebar:
    st.write("## 🛠️ データ同期管理")
    if st.button("🔄 全銘柄のデータを一括更新 (Ubuntu推奨)"):
        with st.status("全銘柄の財務データを取得中...", expanded=True) as status:
            p_cache = load_git_cache()
            for t in all_tickers:
                st.write(f"取得中: {t}...")
                data = get_comprehensive_info(t, AV_API_KEY, force_update=True)
                p_cache[t] = data
            if save_git_cache(p_cache):
                status.update(label="一括取得完了！GitにPushしてください。", state="complete")
                st.success(f"{CACHE_FILE} を更新しました。")

# （以下、ランキング表示や分析パネルのロジックは v5.9 を継承）
# ... [v5.9 と同様のランキング・チャート・シミュレーター・財務詳細コード] ...