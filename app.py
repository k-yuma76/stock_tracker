import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import os
import plotly.graph_objects as go
from datetime import datetime

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="🇺🇸 トレンドトラッカー v6.3", layout="wide")
st.title("🇺🇸 トレンドトラッカー v6.3 🚀")

try:
    AV_API_KEY = st.secrets.get("AV_API_KEY", "")
except Exception:
    AV_API_KEY = ""

CACHE_FILE = "financial_data_cache.csv"

JP_NAME_DICT = {
    "MU": "マイクロン", "PL": "プラネット・ラボ", "TXN": "テキサス・インスツルメンツ",
    "NVDA": "エヌビディア", "TSLA": "テスラ", "OUST": "オースター",
    "AMD": "AMD", "INTC": "インテル", "RDW": "レッドワイヤー", "PLAB": "フォトトロニクス"
}

# --- 2. 共通関数 ---
@st.cache_data
def load_themes_from_csv():
    csv_path = 'themes.csv'
    if not os.path.exists(csv_path): return {}, []
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

def color_val(val):
    if pd.isna(val) or isinstance(val, str): return ''
    return 'color: #00C853; font-weight: bold;' if val > 0 else 'color: #FF5252; font-weight: bold;' if val < 0 else 'color: gray;'

def safe_float(val, default=None):
    try:
        if val in [None, "", "-", "None"]: return default
        return float(val)
    except: return default

def format_large_number(val):
    v = safe_float(val)
    if v is None or v == 0: return "取得不可"
    if v >= 1_000_000_000: return f"${v / 1_000_000_000:.2f}B"
    elif v >= 1_000_000: return f"${v / 1_000_000:.2f}M"
    return f"${v:.2f}"

def format_recommendation(rec_key):
    if not rec_key: return "データなし"
    rec_key = str(rec_key).lower()
    if "strong_buy" in rec_key: return "🟢 強い買い"
    if "buy" in rec_key: return "🟢 買い"
    if "hold" in rec_key: return "🟡 維持"
    if "sell" in rec_key: return "🔴 売り"
    return rec_key.capitalize()

# --- 3. キャッシュ管理 & データ取得 ---
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
        info = yf.Ticker(t).info
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
            if not force_update:
                p_cache[t] = data
                save_git_cache(p_cache)
    except: pass
    return data

# --- 4. サイドバー（同期管理） ---
with st.sidebar:
    st.write("## 🛠️ データ同期管理")
    if st.button("🔄 全銘柄のデータを一括更新"):
        with st.status("財務データを取得中...", expanded=True) as status:
            p_cache = load_git_cache()
            for t in all_tickers:
                st.write(f"取得中: {t}...")
                data = get_comprehensive_info(t, AV_API_KEY, force_update=True)
                p_cache[t] = data
            if save_git_cache(p_cache):
                status.update(label="完了！Git Pushしてください。", state="complete")
                st.success(f"{CACHE_FILE} を更新しました。")

# --- 5. メイン表示部 ---
if themes:
    st.write("### 📅 トレンド集計期間")
    period_options = {"1日": 1, "1週": 5, "2週": 10, "1ヶ月": 30, "3ヶ月": 90}
    sel_p = st.radio("表示期間", list(period_options.keys()), horizontal=True, label_visibility="collapsed")
    days_back = period_options[sel_p]

    @st.cache_data(ttl=3600)
    def fetch_rankings(tickers, days):
        data = yf.download(tickers, period="6mo", progress=False)
        if data.empty: return pd.DataFrame()
        target_idx = -(days + 1) if len(data) > days else 0
        close, volume = data["Close"], data["Volume"]
        ret = ((close.iloc[-1] - close.iloc[target_idx]) / close.iloc[target_idx]) * 100
        vol = ((volume.iloc[-1] - volume.iloc[target_idx]) / volume.iloc[target_idx].replace(0, 1)) * 100
        return pd.DataFrame({"騰落率": ret, "出来高変化": vol}).dropna()

    results = fetch_rankings(all_tickers, days_back)

    if not results.empty:
        theme_summary = [{"テーマ": k, "平均騰落率": results.loc[[t for t in v if t in results.index], "騰落率"].mean(), "平均出来高変化": results.loc[[t for t in v if t in results.index], "出来高変化"].mean()} for k, v in themes.items()]
        df_theme = pd.DataFrame(theme_summary).sort_values("平均騰落率", ascending=False)

        st.write("### 🏆 セクター・ランキング")
        theme_height = int(len(df_theme) * 35.5 + 38)
        sel_theme = st.dataframe(
            df_theme.style.map(color_val, subset=["平均騰落率", "平均出来高変化"]),
            column_config={
                "テーマ": st.column_config.TextColumn("テーマ名", width="medium"),
                "平均騰落率": st.column_config.NumberColumn("騰落率 (%)", format="%+.2f %%", width="small"),
                "平均出来高変化": st.column_config.NumberColumn("出来高 (%)", format="%+.1f %%", width="small")
            },
            height=theme_height, on_select="rerun", selection_mode="single-row", hide_index=True, width="content"
        )

        if sel_theme.selection.rows:
            t_name = df_theme.iloc[sel_theme.selection.rows[0]]["テーマ"]
            st.write(f"### 🔍 **{t_name}** の構成銘柄")
            t_list = [t for t in themes[t_name] if t in results.index]
            df_detail = results.loc[t_list].sort_values("騰落率", ascending=False).reset_index()
            df_detail.columns = ["銘柄", "騰落率", "出来高変化"]
            detail_height = int(len(df_detail) * 35.5 + 38)
            
            sel_stock = st.dataframe(
                df_detail.style.map(color_val, subset=["騰落率", "出来高変化"]),
                column_config={
                    "銘柄": st.column_config.TextColumn("銘柄", width="small"),
                    "騰落率": st.column_config.NumberColumn("騰落率 (%)", format="%+.2f %%", width="small"),
                    "出来高変化": st.column_config.NumberColumn("出来高 (%)", format="%+.1f %%", width="small")
                },
                height=detail_height, on_select="rerun", selection_mode="single-row", hide_index=True, width="content"
            )

            if sel_stock.selection.rows:
                ticker = df_detail.iloc[sel_stock.selection.rows[0]]["銘柄"]
                st.markdown("---")
                st.write(f"### 📈 **{ticker}** ({JP_NAME_DICT.get(ticker, ticker)}) 詳細パネル")

                # 【復活】チャート期間の選択肢
                chart_col_sel, _ = st.columns([1, 2])
                with chart_col_sel:
                    chart_period = st.selectbox("チャート期間", ["1日", "1週間", "1ヶ月", "3ヶ月", "6ヶ月", "1年"], index=2)
                    period_map = {
                        "1日": ("1d", "5m"), "1週間": ("5d", "60m"), "1ヶ月": ("1mo", "1d"), 
                        "3ヶ月": ("3mo", "1d"), "6ヶ月": ("6mo", "1d"), "1年": ("1y", "1d")
                    }
                    y_p, y_i = period_map[chart_period]

                info = get_comprehensive_info(ticker, AV_API_KEY)
                hist = yf.Ticker(ticker).history(period=y_p, interval=y_i)
                
                if not hist.empty:
                    col1, col2 = st.columns([2, 1])
                    curr_val = hist['Close'].iloc[-1]
                    with col1:
                        # 【復活】以前の質感とアノテーションを備えたチャート
                        fig = go.Figure(data=[go.Candlestick(
                            x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'],
                            increasing_line_color='#00C853', decreasing_line_color='#FF5252'
                        )])
                        
                        # 土日や時間外の空白を埋める
                        breaks = [dict(bounds=["sat", "mon"])]
                        if y_i in ["5m", "60m"]: breaks.append(dict(bounds=[16, 9.5], pattern="hour"))
                        fig.update_xaxes(rangebreaks=breaks)
                        
                        # 価格ラベル（高値・安値・現在値）
                        max_v, min_v = hist['High'].max(), hist['Low'].min()
                        max_idx, min_idx = hist['High'].idxmax(), hist['Low'].idxmin()
                        
                        fig.add_annotation(x=max_idx, y=max_v, text=f"高値: ${max_v:.2f}", showarrow=True, arrowhead=1, ax=0, ay=-30, font=dict(color="#00C853"), bgcolor="rgba(0,0,0,0.6)")
                        fig.add_annotation(x=min_idx, y=min_val if (min_val:=min_v) else 0, text=f"安値: ${min_v:.2f}", showarrow=True, arrowhead=1, ax=0, ay=30, font=dict(color="#FF5252"), bgcolor="rgba(0,0,0,0.6)")
                        fig.add_annotation(x=hist.index[-1], y=curr_val, text=f"現在: ${curr_val:.2f}", showarrow=True, arrowhead=1, ax=-50, ay=0, font=dict(color="white"), bgcolor="rgba(0,0,0,0.6)")
                        
                        fig.update_layout(height=480, margin=dict(l=10,r=10,t=10,b=10), xaxis_rangeslider_visible=False)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        st.write("#### 📊 業績 & 評価")
                        st.info(f"推奨: **{format_recommendation(info.get('rec'))}**")
                        t_mean = safe_float(info.get("t_mean"))
                        if t_mean:
                            st.write(f"- 目標株価(平均): `${t_mean:.2f}` ({((t_mean-curr_val)/curr_val)*100:+.1f}%)")
                        
                        eps, f_eps = safe_float(info.get("eps")), safe_float(info.get("f_eps"))
                        st.write(f"- 実績 PER: {f'{(curr_val/eps):.2f}' if eps else '不可'} 倍")
                        st.write(f"- 予想 PER: {f'{(curr_val/f_eps):.2f}' if f_eps else '不可'} 倍")

                        st.markdown("---")
                        st.write("#### 💰 適正株価シミュレーター")
                        input_eps = st.number_input("予想EPS ($)", value=max(0.01, f_eps if f_eps else (eps if eps else 0.01)), step=0.1)
                        input_per = st.number_input("ターゲットPER (倍)", value=max(1.0, (curr_val/eps) if (eps and eps>0) else 15.0), step=1.0)
                        fair_val = input_eps * input_per
                        st.metric("理論株価", f"${fair_val:.2f}", f"{((fair_val - curr_val) / curr_val) * 100:+.1f}%")
                        st.caption(f"ソース: {info.get('source', '不明')} (更新: {info.get('updated_at', '-')})")
