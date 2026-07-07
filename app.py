import pandas as pd
import yfinance as yf
import ta
import streamlit as st
import plotly.graph_objects as gr
import plotly.express as px
from plotly.subplots import make_subplots
import urllib.request
import numpy as np

# הגדרת עיצוב העמוד ומצב כהה (Dark Mode) כברירת מחדל
st.set_page_config(layout="wide", page_title="OBV Quant Matrix Ultra", page_icon="🏆")

# עיצוב כותרות ומראה כללי עם CSS (התאמה מלאה לעברית וימין-לשמאל)
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/calibri');
    
    .main-title { font-size: 36px; font-weight: bold; color: #1E90FF; margin-bottom: 5px; text-align: right; font-family: 'Calibri', sans-serif; }
    .sub-title { font-size: 18px; color: #A0A0A0; margin-bottom: 25px; text-align: right; font-family: 'Calibri', sans-serif; }
    .stButton>button { background-color: #1E90FF; color: white; width: 100%; font-size: 16px; border-radius: 8px; font-weight: bold; font-family: 'Calibri', sans-serif; }
    div[data-testid="stMarkdownContainer"] > p { text-align: right; font-family: 'Calibri', sans-serif; }
    </style>
""", unsafe_allow_html=True)

st.title("🏆 מערכת OBV מתקדמת: Pro-Quant Matrix Ultra")

# --- פונקציה להבאת רשימת סיmולים וסקטורים מוויקיפדיה ---
@st.cache_data(ttl=86400)
def get_us_symbols_with_sectors():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    symbol_to_sector = {}
    
    # S&P 500
    try:
        req = urllib.request.Request('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
        with urllib.request.urlopen(req) as response:
            df_sp = pd.read_html(response.read())[0]
            sym_col = [col for col in df_sp.columns if 'symbol' in str(col).lower() or 'ticker' in str(col).lower()]
            sec_col = [col for col in df_sp.columns if 'sector' in str(col).lower() or 'industry' in str(col).lower()]
            
            if sym_col:
                s_col = sym_col[0]
                sub_col = sec_col[0] if sec_col else None
                for _, row in df_sp.iterrows():
                    sym = str(row[s_col]).strip().upper().replace(".", "-")
                    sec = str(row[sub_col]).strip() if sub_col else "S&P 500"
                    if sym.replace("-", "").isalpha() and len(sym) < 6:
                        symbol_to_sector[sym] = sec
    except Exception:
        pass

    # Nasdaq 100
    try:
        req = urllib.request.Request('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers)
        with urllib.request.urlopen(req) as response:
            html_tables = pd.read_html(response.read())
            for table in html_tables:
                if any('ticker' in str(col).lower() or 'symbol' in str(col).lower() for col in table.columns):
                    sym_col = [col for col in table.columns if 'ticker' in str(col).lower() or 'symbol' in str(col).lower()][0]
                    for sym in table[sym_col].tolist():
                        sym_clean = str(sym).strip().upper().replace(".", "-")
                        if sym_clean.replace("-", "").isalpha() and len(sym_clean) < 6:
                            if sym_clean not in symbol_to_sector:
                                symbol_to_sector[sym_clean] = "Nasdaq Tech"
                    break
    except Exception:
        pass
        
    if not symbol_to_sector:
        default_stocks = {"AAPL":"Technology", "MSFT":"Technology", "GOOGL":"Communication Services", 
                          "AMZN":"Consumer Cyclical", "META":"Communication Services", "NVDA":"Technology"}
        return default_stocks
    return symbol_to_sector

# פונקציות להורדת נתונים מרוכזת
@st.cache_data(ttl=3600)
def load_scanner_data(symbols):
    all_tickers = symbols + ["SPY", "^VIX"]
    return yf.download(all_tickers, period="6mo", interval="1d", group_by='ticker', progress=False, auto_adjust=True)

@st.cache_data(ttl=86400)
def load_backtest_data(symbols):
    all_tickers = symbols + ["SPY", "^VIX"]
    return yf.download(all_tickers, period="2y", interval="1d", group_by='ticker', progress=False, auto_adjust=True)

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

# יצירת הלשוניות
tab1, tab2 = st.tabs(["🔍 סורק מניות ומגמות בזמן אמת", "🔬 מעבדת אופטימיזציה קוואנטית (70%+)"])

stock_sector_dict = get_us_symbols_with_sectors()
symbols = sorted(list(stock_sector_dict.keys()))

# אתחול משתנה הסטייט עבור הסינון הגרפי הדינמי בלשונית 1
if 'selected_sector' not in st.session_state:
    st.session_state['selected_sector'] = "כל השוק"

# ==========================================
# לשונית 1: המפה, גרף ה-XY המשופר והטבלאות
# ==========================================
with tab1:
    st.write("מפת שוק דינמית בסגנון TradingView המציגה עוצמת OBV, יחד עם פאנל מגמות היסטורי נקי מרעשים לזיהוי רוטציית סקטורים.")
    
    if st.button("🚀 הרץ סורק שוק ומגמות בזמן אמת"):
        with st.spinner("מוריד ומנתח נתוני שוק נוכחיים והיסטוריים... אנא המתן."):
            data = load_scanner_data(symbols)
            
            all_results = []
            raw_rows = []
            daily_status_list = []
            
            # שלב ראשון: חישוב אינדיקטורים בסיסיים והיסטוריים לכל מניה
            for symbol in symbols:
                if symbol in ["SPY", "^VIX"]: continue
                try:
                    if symbol not in data.columns.levels[0]: continue
                    df = data[symbol].dropna().copy()
                    if len(df) < 40: continue
                    
                    close = df["Close"].squeeze()
                    volume = df["Volume"].squeeze()
                    
                    obv_series = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
                    obv_sma = obv_series.rolling(14).mean()
                    
                    df["OBV"] = obv_series
                    df["OBV_SMA"] = obv_sma
                    
                    is_above_now = obv_series.iloc[-1] > obv_sma.iloc[-1]
                    sec = stock_sector_dict.get(symbol, "General")
                    
                    # שמירת היסטוריית 30 ימי מסחר אחרונים לטובת ה-XY
                    is_above_series = obv_series > obv_sma
                    last_30_days = is_above_series.tail(30)
                    for date, status in last_30_days.items():
                        daily_status_list.append({
                            "Date": date,
                            "Sector": sec,
                            "Is_Positive": 1 if status else 0
                        })
                    
                    above_series = obv_series > obv_sma
                    consecutive_days = 0
                    for val in reversed(above_series):
                        if val: consecutive_days += 1
                        else: break
                    
                    pct_change_since_cross = 0.0
                    if consecutive_days > 0 and consecutive_days < len(df):
                        cross_day_price = close.iloc[-consecutive_days]
                        pct_change_since_cross = ((close.iloc[-1] - cross_day_price) / cross_day_price) * 100
                    
                    estimated_cap = int(close.iloc[-1] * volume.rolling(20).mean().iloc[-1])
                    if pd.isna(estimated_cap) or estimated_cap <= 0: estimated_cap = 1000000
                    
                    raw_rows.append({
                        "מניה": symbol,
                        "סקטור_בסיס": sec,
                        "is_above": is_above_now,
                        "ימים ברצף": consecutive_days if is_above_now else -consecutive_days,
                        "מחיר ($)": round(close.iloc[-1], 2),
                        "שינוי (%)": round(pct_change_since_cross, 2) if is_above_now else round(((close.iloc[-1] - close.iloc[-2])/close.iloc[-2])*100, 2),
                        "גודל חברה": estimated_cap,
                        "df_data": df
                    })
                except Exception:
                    continue
            
            # שלב שני: עיבוד גרף המגמות והחלקת רעשים
            df_daily = pd.DataFrame(daily_status_list)
            df_trends = df_daily.groupby(["Date", "Sector"])["Is_Positive"].mean().reset_index()
            df_trends["Positive_Pct"] = df_trends["Is_Positive"] * 100
            
            # החלקת קו המגמה בעזרת ממוצע נע של 3 ימים לכל סקטור כדי למנוע קפיצות עצבניות
            df_trends["Positive_Pct_Smoothed"] = df_trends.groupby("Sector")["Positive_Pct"].transform(lambda x: x.rolling(3, min_periods=1).mean())
            
            latest_date = df_trends["Date"].max()
            df_latest = df_trends[df_trends["Date"] == latest_date]
            sector_pct_dict = dict(zip(df_latest["Sector"], df_latest["Positive_Pct"]))
            
            # שלב שלישי: הכנת הנתונים הסופיים ל-Treemap ולטבלאות
            treemap_data = []
            for row in raw_rows:
                sec = row["סקטור_בסיס"]
                pct_pos = sector_pct_dict.get(sec, 0.0)
                sector_extended_name = f"{sec} ({pct_pos:.1f}% Positive)"
                
                treemap_data.append({
                    "מניה": row["מניה"],
                    "סקטור": sector_extended_name,
                    "סקטור_מקורי": sec,
                    "ימים ברצף": row["ימים ברצף"],
                    "מחיר ($)": row["מחיר ($)"],
                    "שינוי (%)": row["שינוי (%)"],
                    "גודל חברה": row["גודל חברה"]
                })
                
                if row["is_above"] and row["מחיר ($)"] >= 5:
                    all_results.append({
                        "מניה": row["מניה"],
                        "סקטור": sec,
                        "מחיר אחרון ($)": row["מחיר ($)"],
                        "ימים מעל ממוצע": row["ימים ברצף"],
                        "שינוי מאז החצייה (%)": row["שינוי (%)"],
                        "מחזור מסחר (Volume)": int(row["df_data"]["Volume"].iloc[-1]),
                        "raw_data": row["df_data"]
                    })
            
            st.session_state['scan_sector_results'] = all_results
            st.session_state['treemap_results'] = treemap_data
            st.session_state['trend_results'] = df_trends
            st.success("הסריקה והניתוח הושלמו בהצלחה!")

    if 'scan_sector_results' in st.session_state and 'treemap_results' in st.session_state:
        results = st.session_state['scan_sector_results']
        map_data = st.session_state['treemap_results']
        trends_df = st.session_state['trend_results']
        
        # 1. הצגת ה-Treemap בסגנון המבוקש
        if map_data:
            st.markdown("### 🗺️ מפת שוק אינטראקטיבית (Treemap)")
            df_map = pd.DataFrame(map_data)
            
            fig_map = px.treemap(
                df_map,
                path=['סקטור', 'מניה'],
                values='גודל חברה',
                color='ימים ברצף',
                color_continuous_scale='Geyser',
                custom_data=['מחיר ($)', 'שינוי (%)', 'סקטור_מקורי']
            )
            
            fig_map.update_traces(
                textinfo="label+value",
                texttemplate="<b>%{label}</b><br>%{customdata[1]}%<br>$%{customdata[0]}",
                hovertemplate="<b>מניה: %{label}</b><br>מחיר: $%{customdata[0]}<br>שינוי: %{customdata[1]}%",
                textposition="middle center",
                textfont=dict(family="Calibri", size=18, color="white")
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

        # 2. פתרון בעיית הבלאגן: הצגת גרף המגמות המשופר (Highlight & Subplots)
        if trends_df is not None and not trends_df.empty:
            st.markdown("### 📈 פאנל מגמות סקטוריאלי נקי מרעשים (30 ימי מסחר אחרונים)")
            
            # פיצ'ר א': תיבת בחירה להבלטה מהירה של סקטור ספציפי על הגרף המרכזי
            unique_sectors = sorted(trends_df["Sector"].unique())
            highlighted_sector = st.selectbox("🎯 בחר סקטור להבלטה ממוקדת על פני השוק (השאר יתעממו ברקע):", ["הצג את כולם שווה בשווה"] + unique_sectors)
            
            fig_trend = gr.Figure()
            
            for sec in unique_sectors:
                df_sec = trends_df[trends_df["Sector"] == sec]
                
                # קביעת עובי וצבע דינמי בהתאם לבחירת המשתמש
                if highlighted_sector == "הצג את כולם שווה בשווה":
                    color_wire = None # נותן ל-Plotly לחלק צבעים כרגיל
                    width_wire = 2.5
                    opacity_wire = 1.0
                elif sec == highlighted_sector:
                    color_wire = "#00EE76" # ירוק בוהק בולט לסקטור הנבחר
                    width_wire = 4.5
                    opacity_wire = 1.0
                else:
                    color_wire = "rgba(100, 100, 100, 0.25)" # אפור מעומעם וכמעט שקוף לכל השאר
                    width_wire = 1.5
                    opacity_wire = 0.4
                    
                fig_trend.add_trace(gr.Scatter(
                    x=df_sec["Date"],
                    y=df_sec["Positive_Pct_Smoothed"], # משתמשים בגרף המוחלק
                    name=sec,
                    mode="lines+markers",
                    line=dict(width=width_wire, color=color_wire),
                    marker=dict(size=4),
                    opacity=opacity_wire,
                    hovertemplate=f"<b>{sec}</b><br>תאריך: %{{x|%Y-%m-%d}}<br>חיוביות: %{{y:.1f}}%<extra></extra>"
                ))
                
            fig_trend.update_layout(
                template="plotly_dark", height=400, hovermode="x unified",
                xaxis=dict(title="ציר הזמן"), yaxis=dict(title="מניות חיוביות (%)", range=[-5, 105]),
                margin=dict(l=10, r=10, t=15, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_trend, use_container_width=True)
            
            # פיצ'ר ב': פילטר תצוגה מהיר לטבלה למטה
            if highlighted_sector != "הצג את כולם שווה בשווה":
                if st.button(f"🔎 סנן את הטבלה למטה רק עבור מניות {highlighted_sector}"):
                    st.session_state['selected_sector'] = highlighted_sector

            if st.button("🌐 אפס סינון והצג את כל המניות בטבלה"):
                st.session_state['selected_sector'] = "כל השוק"
                st.rerun()

        # 3. הצגת טבלת המניות והגרף הטכני התחתון
        if results:
            df_res = pd.DataFrame(results)
            current_filter = st.session_state['selected_sector']
            
            if current_filter != "כל השוק" and current_filter in df_res["סקטור"].unique():
                df_filtered = df_res[df_res["סקטור"] == current_filter].copy()
                st.markdown(f"### 📋 תוצאות עבור הסקטור הנבחר: **{current_filter}**")
            else:
                df_filtered = df_res.copy()
                st.markdown("### 📋 תוצאות סריקה: **כל המניות החיוביות בשוק**")
                
            df_filtered = df_filtered.sort_values(by=["ימים מעל ממוצע"], ascending=False)
            display_cols = ["מניה", "סקטור", "מחיר אחרון ($)", "ימים מעל ממוצע", "שינוי מאז החצייה (%)", "מחזור מסחר (Volume)"]
            
            event = st.dataframe(df_filtered[display_cols].set_index("מניה"), use_container_width=True, on_select="rerun", selection_mode="single-row")
            
            if not df_filtered.empty:
                try:
                    selected_symbol = df_filtered.iloc[event.selection.rows[0]]["מניה"] if event and event.selection and event.selection.rows else df_filtered.iloc[0]["מניה"]
                except Exception:
                    selected_symbol = df_filtered.iloc[0]["מניה"]
                
                if selected_symbol:
                    st.markdown(f"### 🎯 ניתוח טכני ממוקד: **{selected_symbol}**")
                    matched_row = next(item for item in results if item["מניה"] == selected_symbol)
                    df_plot = matched_row["raw_data"]
                    
                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, subplot_titles=("מחיר מניה (Candlestick)", "מדד זרימת נפח (OBV & SMA 14)"))
                    fig.add_trace(gr.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name='מחיר'), row=1, col=1)
                    fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV'], name='OBV', line=dict(color='#FFA500', width=2.5)), row=2, col=1)
                    fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV_SMA'], name='OBV SMA', line=dict(color='#888888', width=1.5, dash='dash')), row=2, col=1)
                    fig.update_layout(height=500, showlegend=True, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=20, r=20, t=40, b=20))
                    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# לשונית 2: מעבדת אופטימיזציה קוואנטית (ללא שינוי פונקציונלי)
# ==========================================
with tab2:
    st.header("🔬 סורק ומפענח קומבינציות מנצחות (70%+ Win Rate)")
    st.write("לחיצה על הכפתור תבצע הרצה מלאה של כל שילובי המסננים על פני נתונים היסטוריים, ותפלוט טבלה מרוכזת של כל מערכות החוקים שהשיגו מעל 70% הצלחה.")
    
    if st.button("🧬 הרץ סריקה מטריציונית מלאה"):
        with st.spinner("מחשב ומנתח נתונים היסטוריים..."):
            bt_data = load_backtest_data(symbols)
            
            if "SPY" not in bt_data.columns.levels[0] or "^VIX" not in bt_data.columns.levels[0]:
                st.error("שגיאה בטעינת מדדי השוק.")
            else:
                df_spy = bt_data["SPY"].dropna().copy()
                df_spy["SMA_50"] = df_spy["Close"].squeeze().rolling(50).mean()
                df_vix = bt_data["^VIX"].dropna().copy()
                
                all_stock_rows = []
                for symbol in symbols:
                    if symbol in ["SPY", "^VIX"]: continue
                    try:
                        if symbol not in bt_data.columns.levels[0]: continue
                        df = bt_data[symbol].dropna().copy()
                        if len(df) < 245: continue
                        close = df["Close"].squeeze()
                        volume = df["Volume"].squeeze()
                        high = df["High"].squeeze()
                        low = df["Low"].squeeze()
                        open_p = df["Open"].squeeze()
                        
                        obv_series = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
                        obv_sma = obv_series.rolling(14).mean()
                        df["OBV"] = obv_series
                        df["OBV_SMA"] = obv_sma
                        df["is_above"] = df["OBV"] > df["OBV_SMA"]
                        df["days_above"] = df["is_above"].groupby((df["is_above"] != df["is_above"].shift()).cumsum()).cumsum() * df["is_above"]
                        
                        df["SMA_200"] = close.rolling(200).mean()
                        df["SMA_50_Stock"] = close.rolling(50).mean()
                        df["Max_High_10D"] = high.shift(1).rolling(10).max()
                        df["CMF"] = ta.volume.ChaikinMoneyFlowIndicator(high, low, close, volume, window=20).chaikin_money_flow()
                        df["Vol_SMA20"] = volume.rolling(20).mean()
                        df["RVOL_Check"] = volume > (df["Vol_SMA20"] * 1.5)
                        df["ATR_14"] = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
                        df["Daily_Range"] = high - low
                        df["ATR_Check"] = df["Daily_Range"] > (df["ATR_14"] * 1.5)
                        prev_close = close.shift(1)
                        df["Gap_Pct"] = ((open_p - prev_close) / prev_close) * 100
                        df["Gap_Check"] = (df["Gap_Pct"] >= 0.5) & (df["Gap_Pct"] <= 5.0)
                        df["Above_SMA50"] = close > df["SMA_50_Stock"]
                        
                        df = df.join(df_spy[["Close", "SMA_50"]], rsuffix="_spy", how="inner")
                        df = df.join(df_vix["Close"], rsuffix="_vix", how="inner")
                        
                        for fd in range(1, 31):
                            df[f"ret_{fd}"] = ((df["Close"].shift(-fd) - df["Close"]) / df["Close"]) * 100
                            
                        clean_cols = [f"ret_{fd}" for fd in range(1, 31)] + ["SMA_200", "CMF", "Max_High_10D", "SMA_50", "Close_vix", "ATR_Check", "Gap_Check", "Above_SMA50"]
                        df = df.dropna(subset=clean_cols)
                        if not df.empty:
                            all_stock_rows.append(df[["days_above", "SMA_200", "Max_High_10D", "CMF", "Close_spy", "SMA_50", "Close", "RVOL_Check", "Close_vix", "ATR_Check", "Gap_Check", "Above_SMA50"] + [f"ret_{fd}" for fd in range(1, 31)]])
                    except Exception:
                        continue
                        
                if all_stock_rows:
                    master_large_df = pd.concat(all_stock_rows)
                    breadth_df = pd.DataFrame(master_large_df.groupby(master_large_df.index)['Above_SMA50'].mean() * 100).rename(columns={'Above_SMA50': 'Market_Breadth_Pct'})
                    master_df = master_large_df.join(breadth_df, how="inner").reset_index()
                    
                    master_df['filter_trend'] = master_df['Close'] > master_df['SMA_200']
                    master_df['filter_market'] = master_df['Close_spy'] > master_df['SMA_50']
                    master_df['filter_break'] = master_df['Close'] > master_df['Max_High_10D']
                    master_df['filter_cmf'] = master_df['CMF'] > 0
                    master_df['filter_rvol'] = master_df['RVOL_Check'] == True
                    master_df['filter_vix'] = master_df['Close_vix'] < 20.0
                    master_df['filter_atr'] = master_df['ATR_Check'] == True
                    master_df['filter_gap'] = master_df['Gap_Check'] == True
                    master_df['filter_breadth'] = master_df['Market_Breadth_Pct'] > 55.0
                    
                    import itertools
                    combinations = list(itertools.product([True, False], repeat=9))
                    table_rows = []
                    
                    for target_day in [1, 2, 3]:
                        day_mask = master_df['days_above'] == target_day
                        df_day = master_df[day_mask]
                        if df_day.empty: continue
                        
                        for combo in combinations:
                            mask = np.ones(len(df_day), dtype=bool)
                            if combo[0]: mask &= df_day['filter_trend']
                            if combo[1]: mask &= df_day['filter_market']
                            if combo[2]: mask &= df_day['filter_break']
                            if combo[3]: mask &= df_day['filter_cmf']
                            if combo[4]: mask &= df_day['filter_rvol']
                            if combo[5]: mask &= df_day['filter_vix']
                            if combo[6]: mask &= df_day['filter_atr']
                            if combo[7]: mask &= df_day['filter_gap']
                            if combo[8]: mask &= df_day['filter_breadth']
                            
                            sub_df = df_day[mask]
                            samples = len(sub_df)
                            
                            if samples < 30: continue
                                
                            win_rates = (sub_df[[f'ret_{fd}' for fd in range(1, 31)]] > 0).mean() * 100
                            max_wr = win_rates.max()
                            best_fd = int(win_rates.idxmax().split('_')[1])
                            
                            if max_wr >= 70.0:
                                table_rows.append({
                                    "תזמון (ימי רצף)": f"יום {target_day}",
                                    "סיכוי הצלחה שיא": f"{max_wr:.2f}%",
                                    "יום יציאה אופטימלי": f"יום {best_fd}",
                                    "כמות מקרים (Samples)": samples,
                                    "מערכת חוקים פעילה": get_active_filters_text(combo)
                                })
                                
                    if table_rows:
                        df_all_winners = pd.DataFrame(table_rows).sort_values(by="סיכוי הצלחה שיא", ascending=False)
                        st.subheader(f"📊 נמצאו {len(df_all_winners)} שילובים שונים שעברו את רף ה-70%!")
                        st.caption("הטבלה ממוינת מההסתברות הגבוהה ביותר לנמוכה ביותר. כל השורות עומדות בדרישות מובהקות סטטיסטית (N >= 30).")
                        st.dataframe(df_all_winners.set_index("תזמון (ימי רצף)"), use_container_width=True)
                    else:
                        st.warning("לא נמצאו קומבינציות שעברו את רף ה-70% ועמדו במגבלת הדגימות המינימלית (30 מקרים).")
                else:
                    st.error("לא נאספו מספיק נתונים לביצוע הניתוח המורחב.")
