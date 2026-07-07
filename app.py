import pandas as pd
import yfinance as yf
import ta
import streamlit as st
import plotly.graph_objects as gr
import plotly.express as px
from plotly.subplots import make_subplots
import urllib.request
import numpy as np
import itertools
from scipy import stats
import io

# ==========================================
# הגדרות עמוד
# ==========================================
st.set_page_config(layout="wide", page_title="OBV Quant Matrix Ultra", page_icon="🏆")

st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/calibri');
    .main-title { font-size: 36px; font-weight: bold; color: #1E90FF; margin-bottom: 5px; text-align: right; font-family: 'Calibri', sans-serif; }
    .sub-title { font-size: 18px; color: #A0A0A0; margin-bottom: 25px; text-align: right; font-family: 'Calibri', sans-serif; }
    .stButton>button { background-color: #1E90FF; color: white; width: 100%; font-size: 16px; border-radius: 8px; font-weight: bold; font-family: 'Calibri', sans-serif; }
    div[data-testid="stMarkdownContainer"] > p { text-align: right; font-family: 'Calibri', sans-serif; }
    .metric-card { background: #1a1a2e; border-radius: 10px; padding: 12px 18px; border-left: 4px solid #1E90FF; margin: 4px 0; }
    </style>
""", unsafe_allow_html=True)

st.title("🏆 מערכת OBV מתקדמת: Pro-Quant Matrix Ultra")

# ==========================================
# סיידבר: פרמטרים גלובליים ניתנים לשינוי
# ==========================================
with st.sidebar:
    st.header("⚙️ פרמטרים גלובליים")
    obv_sma_period = st.slider("תקופת OBV SMA", min_value=5, max_value=50, value=14, step=1,
                               help="ממוצע נע של OBV – ברירת מחדל 14 ימים")
    rsi_period = st.slider("תקופת RSI", min_value=7, max_value=21, value=14, step=1)
    rvol_multiplier = st.slider("מכפיל RVOL (נפח חריג)", min_value=1.2, max_value=3.0, value=1.5, step=0.1,
                                help="כמה גדול יותר הנפח ביחס לממוצע 20 ימים")
    min_price_filter = st.number_input("מחיר מינימלי ($)", min_value=1.0, max_value=50.0, value=5.0, step=1.0)
    min_samples_bt = st.slider("מינימום דגימות (Backtest)", min_value=15, max_value=100, value=30, step=5)
    win_rate_threshold = st.slider("רף Win Rate (%)", min_value=55, max_value=85, value=70, step=5)
    st.divider()
    st.caption("שינוי הפרמטרים ישפיע על כל החישובים בכל הלשוניות.")

# ==========================================
# פונקציית חישוב ניקוד כוללת (1–10) לכל מניה
# ==========================================
def compute_stock_score(df_stock, obv_sma_p=14, rsi_p=14, rvol_mult=1.5):
    """
    מחזיר ניקוד 1–10 לפי אינדיקטורים טכניים מרובים.
    """
    score = 0
    close = df_stock["Close"].squeeze()
    volume = df_stock["Volume"].squeeze()
    high = df_stock["High"].squeeze()
    low = df_stock["Low"].squeeze()

    try:
        # OBV מעל SMA
        obv = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
        if obv.iloc[-1] > obv.rolling(obv_sma_p).mean().iloc[-1]:
            score += 2

        # RSI: אזור כוח (50-70) — לא קנוי יתר
        rsi = ta.momentum.RSIIndicator(close, window=rsi_p).rsi().iloc[-1]
        if 50 < rsi < 70:
            score += 2
        elif rsi >= 70:
            score += 0

        # מחיר מעל SMA200 (בדיקה בטוחה שיש מספיק נתונים)
        if len(close) >= 200:
            sma200 = close.rolling(200).mean()
            if not pd.isna(sma200.iloc[-1]) and close.iloc[-1] > sma200.iloc[-1]:
                score += 1

        # CMF חיובי
        cmf = ta.volume.ChaikinMoneyFlowIndicator(high, low, close, volume, window=20).chaikin_money_flow().iloc[-1]
        if cmf > 0:
            score += 1

        # RVOL גבוה
        vol_sma20 = volume.rolling(20).mean().iloc[-1]
        if volume.iloc[-1] > vol_sma20 * rvol_mult:
            score += 1

        # RSI Divergence: מחיר עולה, RSI יורד
        rsi_series = ta.momentum.RSIIndicator(close, window=rsi_p).rsi()
        price_up = close.iloc[-1] > close.iloc[-5]
        rsi_down = rsi_series.iloc[-1] < rsi_series.iloc[-5]
        if price_up and not rsi_down:
            score += 1
        elif price_up and rsi_down:
            score -= 1

        # ATR Expansion
        atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
        daily_range = (high - low).iloc[-1]
        if daily_range > atr.iloc[-1] * 1.5:
            score += 1

        # Relative Strength vs SPY
        if "Close_spy" in df_stock.columns:
            ret_stock = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0
            ret_spy = (df_stock["Close_spy"].iloc[-1] / df_stock["Close_spy"].iloc[-20] - 1) * 100 if len(df_stock) >= 20 else 0
            if ret_stock > ret_spy:
                score += 1
    except Exception:
        pass

    return max(1, min(10, score))

# ==========================================
# חישוב p-value בינומי לאמינות סטטיסטית
# ==========================================
def binomial_pvalue(win_rate_pct, n_samples, null_hypothesis=0.5):
    """
    בודק האם Win Rate גבוה מ-50% באופן מובהק סטטיסטית.
    """
    wins = int(round(win_rate_pct / 100 * n_samples))
    p_value = stats.binom_test(wins, n_samples, null_hypothesis, alternative='greater')
    return p_value

# ==========================================
# פונקציות נתונים דינמיות (S&P 500 + Nasdaq 100)
# ==========================================
@st.cache_data(ttl=86400)
def get_us_symbols_with_sectors():
    """
    מושך באופן דינמי את כל מניות ה-S&P 500 וה-Nasdaq 100 מויקיפדיה,
    מנקה את הטיקרים ובונה מילון סקטורים מלא (סביב 500-600 מניות ייחודיות).
    """
    symbol_to_sector = {}
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')]
    urllib.request.install_opener(opener)

    # 1. משיכת כל מניות ה-S&P 500
    try:
        url_sp = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url_sp)
        df_sp = tables[0]
        
        sym_col = [col for col in df_sp.columns if 'symbol' in str(col).lower() or 'ticker' in str(col).lower()][0]
        sec_col = [col for col in df_sp.columns if 'sector' in str(col).lower() or 'industry' in str(col).lower()][0]
        
        for _, row in df_sp.iterrows():
            sym = str(row[sym_col]).strip().upper().replace(".", "-")
            sec = str(row[sec_col]).strip()
            if sym.replace("-", "").isalpha() and len(sym) < 6:
                symbol_to_sector[sym] = sec
    except Exception as e:
        st.warning(f"⚠️ לא הצלחתי לטעון את ה-S&P 500 מויקיפדיה: {e}")

    # 2. משיכת כל מניות ה-Nasdaq 100
    try:
        url_ndx = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        tables_ndx = pd.read_html(url_ndx)
        
        for table in tables_ndx:
            if any('ticker' in str(col).lower() or 'symbol' in str(col).lower() for col in table.columns):
                sym_col_name = [col for col in table.columns if 'ticker' in str(col).lower() or 'symbol' in str(col).lower()][0]
                sec_col_name = [col for col in table.columns if 'industry' in str(col).lower() or 'sector' in str(col).lower()]
                
                for _, row in table.iterrows():
                    sym = str(row[sym_col_name]).strip().upper().replace(".", "-")
                    sec = str(row[sec_col_name[0]]).strip() if sec_col_name else "Nasdaq Tech"
                    
                    if sym.replace("-", "").isalpha() and len(sym) < 6:
                        if sym not in symbol_to_sector:
                            symbol_to_sector[sym] = sec
                break
    except Exception as e:
        st.warning(f"⚠️ לא הצלחתי לטעון את ה-Nasdaq 100 מויקיפדיה: {e}")

    # 3. מנגנון הגנה למקרה ששני האתרים חסמו
    if not symbol_to_sector:
        return {"AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Communication Services",
                "AMZN": "Consumer Cyclical", "META": "Communication Services", "NVDA": "Technology",
                "TSLA": "Consumer Cyclical", "AVGO": "Technology", "AMD": "Technology", "QCOM": "Technology"}
                
    return symbol_to_sector

@st.cache_data(ttl=3600)
def load_scanner_data(symbols):
    all_tickers = symbols + ["SPY", "^VIX"]
    return yf.download(all_tickers, period="1y", interval="1d", group_by='ticker', progress=False, auto_adjust=False)

@st.cache_data(ttl=86400)
def load_backtest_data(symbols):
    all_tickers = symbols + ["SPY", "^VIX"]
    return yf.download(all_tickers, period="2y", interval="1d", group_by='ticker', progress=False, auto_adjust=False)

def get_active_filters_text(combo):
    filters = []
    if combo[0]: filters.append("מחיר > SMA200")
    if combo[1]: filters.append("SPY > SMA50")
    if combo[2]: filters.append("שיא 10 ימים")
    if combo[3]: filters.append("CMF > 0")
    if combo[4]: filters.append("RVOL (נפח חריג)")
    if combo[5]: filters.append("VIX < 20")
    if combo[6]: filters.append("ATR Expansion")
    if combo[7]: filters.append("Gap-Up")
    if combo[8]: filters.append("רוחב שוק > 55%")
    return " | ".join(filters) if filters else "ללא מסננים (OBV בלבד)"

# ==========================================
# Session State
# ==========================================
stock_sector_dict = get_us_symbols_with_sectors()
symbols = sorted(list(stock_sector_dict.keys()))

if 'selected_sector' not in st.session_state:
    st.session_state['selected_sector'] = "כל השוק"

# ==========================================
# לשוניות האפליקציה
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "🔍 סורק מניות ומגמות בזמן אמת",
    "🔬 מעבדת אופטימיזציה קוואנטית (70%+)",
    "📊 דוח מניות מובילות (Top Picks)"
])

# ==========================================
# לשונית 1: סורק + Treemap + מגמות + ניקוד
# ==========================================
with tab1:
    st.write("מפת שוק דינמית בסגנון TradingView המציגה עוצמת OBV, יחד עם פאנל מגמות היסטורי לזיהוי רוטציית סקטורים.")
    st.caption(f"כמות מניות לניתוח: {len(symbols)} (S&P 500 & Nasdaq 100) | OBV SMA={obv_sma_period}")

    if st.button("🚀 הרץ סורק שוק ומגמות בזמן אמת"):
        with st.spinner(f"מוריד ומנתח {len(symbols)} נתוני שוק במקביל... אנא המתן."):
            data = load_scanner_data(symbols)

            all_results = []
            raw_rows = []
            daily_status_list = []
            failed_count = 0

            if not data.empty:
                try:
                    spy_data = data["SPY"].dropna()
                except Exception:
                    spy_data = pd.DataFrame()

                for symbol in symbols:
                    if symbol in ["SPY", "^VIX"]:
                        continue
                    try:
                        if symbol not in data.columns.levels[0]:
                            failed_count += 1
                            continue
                        df = data[symbol].dropna().copy()
                        if df.empty or len(df) < 40:
                            failed_count += 1
                            continue

                        close = df["Close"].squeeze()
                        volume = df["Volume"].squeeze()
                        high = df["High"].squeeze()
                        low = df["Low"].squeeze()

                        obv_series = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
                        obv_sma = obv_series.rolling(obv_sma_period).mean()

                        df["OBV"] = obv_series
                        df["OBV_SMA"] = obv_sma
                        df["RSI"] = ta.momentum.RSIIndicator(close, window=rsi_period).rsi()
                        df["CMF"] = ta.volume.ChaikinMoneyFlowIndicator(high, low, close, volume, window=20).chaikin_money_flow()
                        df["SMA200"] = close.rolling(200).mean()

                        if not spy_data.empty:
                            df["Close_spy"] = spy_data["Close"]

                        is_above_now = obv_series.iloc[-1] > obv_sma.iloc[-1]
                        sec = stock_sector_dict.get(symbol, "General")

                        is_above_series = obv_series > obv_sma
                        last_30_days = is_above_series.tail(30)
                        for date, status in last_30_days.items():
                            daily_status_list.append({
                                "Date": date,
                                "Sector": sec,
                                "Is_Positive": 1 if status else 0
                            })

                        consecutive_days = 0
                        for val in reversed(is_above_series):
                            if val:
                                consecutive_days += 1
                            else:
                                break

                        pct_change_since_cross = 0.0
                        if consecutive_days > 0 and consecutive_days < len(df):
                            cross_day_price = close.iloc[-consecutive_days]
                            pct_change_since_cross = ((close.iloc[-1] - cross_day_price) / cross_day_price) * 100

                        estimated_cap = int(close.iloc[-1] * volume.rolling(20).mean().iloc[-1])
                        if pd.isna(estimated_cap) or estimated_cap <= 0:
                            estimated_cap = 1_000_000

                        stock_score = compute_stock_score(df, obv_sma_p=obv_sma_period, rsi_p=rsi_period, rvol_mult=rvol_multiplier)

                        raw_rows.append({
                            "מניה": symbol, "סקטור_בסיס": sec, "is_above": is_above_now, "ימים ברצף": consecutive_days if is_above_now else -consecutive_days,
                            "מחיר ($)": round(close.iloc[-1], 2), "RSI": round(df["RSI"].iloc[-1], 1) if not pd.isna(df["RSI"].iloc[-1]) else None,
                            "CMF": round(df["CMF"].iloc[-1], 3) if not pd.isna(df["CMF"].iloc[-1]) else None,
                            "שינוי (%)": round(pct_change_since_cross, 2) if is_above_now else round(((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]) * 100, 2),
                            "גודל חברה": estimated_cap, "ניקוד (1-10)": stock_score, "df_data": df
                        })

                        if is_above_now and close.iloc[-1] >= min_price_filter:
                            all_results.append({
                                "מניה": symbol, "סקטור": sec, "מחיר אחרון ($)": round(close.iloc[-1], 2), "ימים מעל ממוצע": consecutive_days,
                                "שינוי מאז החצייה (%)": round(pct_change_since_cross, 2), "RSI": round(df["RSI"].iloc[-1], 1) if not pd.isna(df["RSI"].iloc[-1]) else None,
                                "CMF": round(df["CMF"].iloc[-1], 3) if not pd.isna(df["CMF"].iloc[-1]) else None, "ניקוד (1-10)": stock_score,
                                "מחזור מסחר (Volume)": int(volume.iloc[-1]), "raw_data": df
                            })
                    except Exception:
                        failed_count += 1
                        continue

            df_daily = pd.DataFrame(daily_status_list)
            df_trends = pd.DataFrame()
            if not df_daily.empty:
                df_trends = df_daily.groupby(["Date", "Sector"])["Is_Positive"].mean().reset_index()
                df_trends["Positive_Pct"] = df_trends["Is_Positive"] * 100
                df_trends["Positive_Pct_Smoothed"] = df_trends.groupby("Sector")["Positive_Pct"].transform(
                    lambda x: x.rolling(3, min_periods=1).mean()
                )

            latest_date = df_trends["Date"].max() if not df_trends.empty else None
            sector_pct_dict = {}
            if latest_date is not None:
                df_latest = df_trends[df_trends["Date"] == latest_date]
                sector_pct_dict = dict(zip(df_latest["Sector"], df_latest["Positive_Pct"]))

            treemap_data = []
            for row in raw_rows:
                sec = row["סקטור_בסיס"]
                pct_pos = sector_pct_dict.get(sec, 0.0)
                sector_extended_name = f"{sec} ({pct_pos:.1f}% Positive)"
                treemap_data.append({
                    "מניה": row["מניה"], "סקטור": sector_extended_name, "סקטור_מקורי": sec, "ימים ברצף": row["ימים ברצף"],
                    "מחיר ($)": row["מחיר ($)"], "שינוי (%)": row["שינוי (%)"], "גודל חברה": row["גודל חברה"], "ניקוד": row["ניקוד (1-10)"]
                })

            st.session_state['scan_sector_results'] = all_results
            st.session_state['treemap_results'] = treemap_data
            st.session_state['trend_results'] = df_trends
            st.session_state['failed_count'] = failed_count
            st.success(f"✅ הסריקה הושלמה! סורקו {len(raw_rows)} מניות. נכשלו: {failed_count}.")

    if 'scan_sector_results' in st.session_state and 'treemap_results' in st.session_state:
        results = st.session_state['scan_sector_results']
        map_data = st.session_state['treemap_results']
        trends_df = st.session_state['trend_results']

        if results:
            df_res_all = pd.DataFrame(results)
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            top_sector = df_res_all.groupby("סקטור").size().idxmax() if not df_res_all.empty else "—"
            avg_score = df_res_all["ניקוד (1-10)"].mean() if "ניקוד (1-10)" in df_res_all.columns else 0
            col_m1.metric("מניות חיוביות", len(results))
            col_m2.metric("מניות שנסרקו", len(map_data))
            col_m3.metric("סקטור מוביל", top_sector)
            col_m4.metric("ניקוד ממוצע", f"{avg_score:.1f} / 10")

        if map_data:
            st.markdown("### 🗺️ מפת שוק אינטראקטיבית (Treemap)")
            df_map = pd.DataFrame(map_data)

            fig_map = px.treemap(
                df_map, path=['סקטור', 'מניה'], values='גודל חברה', color='ימים ברצף',
                color_continuous_scale='Geyser', custom_data=['מחיר ($)', 'שינוי (%)', 'סקטור_מקורי', 'ניקוד']
            )
            fig_map.update_traces(
                textinfo="label+value",
                texttemplate="<b>%{label}</b><br>%{customdata[1]}%<br>$%{customdata[0]}<br>⭐%{customdata[3]}",
                hovertemplate="<b>%{label}</b><br>מחיר: $%{customdata[0]}<br>שינוי: %{customdata[1]}%<br>ניקוד: %{customdata[3]}/10",
                textposition="middle center", textfont=dict(family="Calibri", size=16, color="white")
            )
            fig_map.update_layout(
                template="plotly_dark", height=450, margin=dict(l=10, r=10, t=20, b=10),
                coloraxis=dict(colorbar=dict(title="ימי רצף", thickness=15))
            )

            selected_click = st.plotly_chart(fig_map, use_container_width=True, on_select="rerun")

            if selected_click and 'selection' in selected_click and selected_click['selection']['points']:
                clicked_label = selected_click['selection']['points'][0].get('label', '')
                if clicked_label in symbols:
                    try:
                        st.session_state['selected_sector'] = selected_click['selection']['points'][0].get('customdata', [])[2]
                    except Exception:
                        st.session_state['selected_sector'] = stock_sector_dict.get(clicked_label, "כל השוק")
                else:
                    st.session_state['selected_sector'] = clicked_label.split(" (")[0]

        if trends_df is not None and not trends_df.empty:
            st.markdown("### 📈 פאנל מגמות סקטוריאלי נקי מרעשים (30 ימי מסחר אחרונים)")
            unique_sectors = sorted(trends_df["Sector"].unique())
            highlighted_sector = st.selectbox("🎯 בחר סקטור להבלטה ממוקדת:", ["הצג את כולם שווה בשווה"] + unique_sectors)

            fig_trend = gr.Figure()
            for sec in unique_sectors:
                df_sec = trends_df[trends_df["Sector"] == sec]
                if highlighted_sector == "הצג את כולם שווה בשווה":
                    color_wire, width_wire, opacity_wire = None, 2.5, 1.0
                elif sec == highlighted_sector:
                    color_wire, width_wire, opacity_wire = "#00EE76", 4.5, 1.0
                else:
                    color_wire, width_wire, opacity_wire = "rgba(100,100,100,0.25)", 1.5, 0.4

                fig_trend.add_trace(gr.Scatter(
                    x=df_sec["Date"], y=df_sec["Positive_Pct_Smoothed"], name=sec, mode="lines+markers",
                    line=dict(width=width_wire, color=color_wire), marker=dict(size=4), opacity=opacity_wire,
                    hovertemplate=f"<b>{sec}</b><br>%{{x|%Y-%m-%d}}<br>חיוביות: %{{y:.1f}}%<extra></extra>"
                ))

            fig_trend.update_layout(
                template="plotly_dark", height=400, hovermode="x unified",
                xaxis=dict(title="ציר הזמן"), yaxis=dict(title="מניות חיוביות (%)", range=[-5, 105]),
                margin=dict(l=10, r=10, t=15, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_trend, use_container_width=True)

            if highlighted_sector != "הצג את כולם שווה בשווה":
                if st.button(f"🔎 סנן טבלה למניות {highlighted_sector}"):
                    st.session_state['selected_sector'] = highlighted_sector

            if st.button("🌐 אפס סינון — כל המניות"):
                st.session_state['selected_sector'] = "כל השוק"
                st.rerun()

        if results:
            df_res = pd.DataFrame(results)
            current_filter = st.session_state['selected_sector']

            if current_filter != "כל השוק" and current_filter in df_res["סקטור"].unique():
                df_filtered = df_res[df_res["סקטור"] == current_filter].copy()
                st.markdown(f"### 📋 תוצאות: **{current_filter}**")
            else:
                df_filtered = df_res.copy()
                st.markdown("### 📋 תוצאות סריקה: **כל המניות החיוביות**")

            df_filtered = df_filtered.sort_values(by=["ניקוד (1-10)", "ימים מעל ממוצע"], ascending=False)
            display_cols = ["מניה", "סקטור", "מחיר אחרון ($)", "ימים מעל ממוצע",
                            "שינוי מאז החצייה (%)", "RSI", "CMF", "ניקוד (1-10)", "מחזור מסחר (Volume)"]

            event = st.dataframe(df_filtered[display_cols].set_index("מניה"),
                                 use_container_width=True, on_select="rerun", selection_mode="single-row")

            csv_buffer = io.StringIO()
            df_
