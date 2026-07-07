import pandas as pd
import yfinance as yf
import ta
import streamlit as st
import plotly.graph_objects as gr
import plotly.express as px
from plotly.subplots import make_subplots
import urllib.request

# הגדרת עיצוב העמוד ומצב כהה (Dark Mode) כברירת מחדל
st.set_page_config(layout="wide", page_title="OBV Market Treemap & Trends", page_icon="🏆")

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

st.markdown('<div class="main-title">🏆 מערכת אנליזה: מפת שוק ומגמות סקטורים (OBV)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">ניתוח רוטציית סקטורים בזמן אמת: מפת עץ (Treemap) וגרף מגמה היסטורי רציף לחודש האחרון</div>', unsafe_allow_html=True)

# אתחול משתנה הסטייט עבור הסינון הגרפי הדינמי
if 'selected_sector' not in st.session_state:
    st.session_state['selected_sector'] = "כל השוק"

# --- פונקציה להבאת רשימת סימולים וסקטורים מוויקיפדיה ---
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

# הורדת נתוני מסחר מורחבים (מוגבל ל-120 מניות מובילות לצורך מהירות חישוב ויציבות)
@st.cache_data(ttl=3600)
def load_scanner_data(symbols):
    limited_symbols = symbols[:120] if len(symbols) > 120 else symbols
    return yf.download(limited_symbols, period="6mo", interval="1d", group_by='ticker', progress=False, auto_adjust=True), limited_symbols

stock_sector_dict = get_us_symbols_with_sectors()
all_symbols = sorted(list(stock_sector_dict.keys()))

# כפתור הרצה ראשי
if st.button("🚀 הרץ ניתוח שוק, מפת עץ ומגמות סקטורים"):
    with st.spinner("⚡ מחשב אינדיקטורים ומנתח היסטוריית מגמות חודש אחורה... אנא המתן"):
        data, active_symbols = load_scanner_data(all_symbols)
        all_results = []
        raw_rows = []
        
        # מבנה נתונים זמני לאחסון מצב ה-OBV היומי של כל המניות
        daily_status_list = []

        # חישוב נתונים טכניים בסיסיים
        for symbol in active_symbols:
            try:
                if symbol not in data.columns.levels[0]: continue
                df = data[symbol].dropna().copy()
                if len(df) < 40: continue
                
                close = df["Close"].squeeze()
                volume = df["Volume"].squeeze()
                
                # חישוב אינדיקטורים
                obv_series = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
                obv_sma = obv_series.rolling(14).mean()
                
                df["OBV"] = obv_series
                df["OBV_SMA"] = obv_sma
                
                is_above_now = obv_series.iloc[-1] > obv_sma.iloc[-1]
                sec = stock_sector_dict.get(symbol, "General")
                
                # שמירת מצב היסטורי ב-30 ימים האחרונים לצורך גרף ה-XY
                # מפיקים את סדרת הנתונים של ה-30 ימים האחרונים
                is_above_series = obv_series > obv_sma
                last_30_days = is_above_series.tail(30)
                
                for date, status in last_30_days.items():
                    daily_status_list.append({
                        "Date": date,
                        "Sector": sec,
                        "Symbol": symbol,
                        "Is_Positive": 1 if status else 0
                    })

                # חישוב ימי רצף
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

        # עיבוד נתוני המגמה ההיסטורית (חודש אחורה)
        df_daily = pd.DataFrame(daily_status_list)
        # מחשבים את אחוז המניות החיוביות לכל יום ולכל סקטור
        df_trends = df_daily.groupby(["Date", "Sector"])["Is_Positive"].mean().reset_index()
        df_trends["Positive_Pct"] = df_trends["Is_Positive"] * 100
        
        # חילוץ האחוזים העדכניים ביותר (להוספה לכותרת ה-Treemap)
        latest_date = df_trends["Date"].max()
        df_latest_trends = df_trends[df_trends["Date"] == latest_date]
        sector_pct_dict = dict(zip(df_latest_trends["Sector"], df_trends["Positive_Pct"]))

        # בניית הנתונים הסופיים עבור ה-Treemap והטבלה
        treemap_data = []
        for row in raw_rows:
            sec = row["סקטור_בסיס"]
            pct_pos = sector_counts = sector_pct_dict.get(sec, 0.0)
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

# הצגת הממשק והגרפים
if 'scan_sector_results' in st.session_state and 'treemap_results' in st.session_state and 'trend_results' in st.session_state:
    results = st.session_state['scan_sector_results']
    map_data = st.session_state['treemap_results']
    trends_df = st.session_state['trend_results']
    
    # 1. תצוגת ה-Treemap בסגנון TradingView
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
            template="plotly_dark", height=500, margin=dict(l=10, r=10, t=25, b=10),
            coloraxis=dict(colorbar=dict(title="ימי רצף", thickness=15))
        )
        
        selected_click = st.plotly_chart(fig_map, use_container_width=True, on_select="rerun")
        
        # זיהוי לחיצה ב-Treemap
        if selected_click and 'selection' in selected_click and selected_click['selection']['points']:
            clicked_point = selected_click['selection']['points'][0]
            if 'label' in clicked_point:
                clicked_label = clicked_point['label']
                if clicked_label in all_symbols:
                    try:
                        st.session_state['selected_sector'] = clicked_point.get('customdata', [])[2]
                    except Exception:
                        st.session_state['selected_sector'] = stock_sector_dict.get(clicked_label, "כל השוק")
                else:
                    st.session_state['selected_sector'] = clicked_label.split(" (")[0]

    # 2. תצוגת גרף מגמות רציף XY (Time-Series) לחודש האחרון
    if not trends_df.empty:
        st.markdown("### 📈 גרף מגמות XY: אחוז המניות החיוביות בכל סקטור (30 ימים אחרונים)")
        
        # יצירת גרף קווי רציף עם Plotly Express
        fig_trend = px.line(
            trends_df,
            x="Date",
            y="Positive_Pct",
            color="Sector",
            labels={"Date": "תאריך", "Positive_Pct": "מניות חיוביות (%)", "Sector": "סקטור"},
            markers=True, # הוספת נקודות קטנות על הקו לזיהוי ימי מסחר
            category_orders={"Sector": sorted(trends_df["Sector"].unique())}
        )
        
        fig_trend.update_traces(
            line=dict(width=3), 
            marker=dict(size=6),
            hovertemplate="<b>סקטור: %{legendgroup}</b><br>תאריך: %{x|%Y-%m-%d}<br>חיוביות: %{y:.1f}%"
        )
        
        fig_trend.update_layout(
            template="plotly_dark",
            height=450,
            hovermode="x unified", # קו אנכי מאוחד שמציג את כל הסקטורים יחד כשעומדים על תאריך
            xaxis=dict(title="ציר הזמן (חודש אחורה)", showgrid=True),
            yaxis=dict(title="אחוז המניות עם OBV חיובי (%)", range=[0, 105], showgrid=True),
            margin=dict(l=10, r=10, t=20, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        # הצגת הגרף וזיהוי לחיצות על הקווים/מקרא לסנכרון הטבלה
        trend_click = st.plotly_chart(fig_trend, use_container_width=True, on_select="rerun")
        
        if trend_click and 'selection' in trend_click and trend_click['selection']['points']:
            # שליפת שם הסקטור מתוך החלק שנלחץ בגרף הקווי
            try:
                clicked_legend_sector = trend_click['selection']['points'][0].get('customdata', [None])[0]
                if not clicked_legend_sector:
                    # שיטת גיבוי דרך מספר הסדרה (Trace index)
                    trace_idx = trend_click['selection']['points'][0]['trace_index']
                    clicked_legend_sector = sorted(trends_df["Sector"].unique())[trace_idx]
                if clicked_legend_sector:
                    st.session_state['selected_sector'] = clicked_legend_sector
            except Exception:
                pass

        # כפתור איפוס מהיר
        if st.button("🌐 אפס סינון והצג את כל המניות שנמצאו"):
            st.session_state['selected_sector'] = "כל השוק"
            st.rerun()

    # 3. הצגת טבלת המניות והגרף הטכני התחתון
    if results:
        df_res = pd.DataFrame(results)
        current_filter = st.session_state['selected_sector']
        
        if current_filter != "כל השוק" and current_filter in df_res["סקטור"].unique():
            df_filtered = df_res[df_res["סקטור"] == current_filter].copy()
            st.markdown(f"### 📋 תוצאות סריקה עבור הסקטור שנבחר: **{current_filter}**")
        else:
            df_filtered = df_res.copy()
            st.markdown("### 📋 תוצאות סריקה: **כל המניות החיוביות בשוק**")
            
        df_filtered = df_filtered.sort_values(by=["ימים מעל ממוצע"], ascending=False)
        display_cols = ["מניה", "סקטור", "מחיר אחרון ($)", "ימים מעל ממוצע", "שינוי מאז החצייה (%)", "מחזור מסחר (Volume)"]
        
        event = st.dataframe(
            df_filtered[display_cols].set_index("מניה"), 
            use_container_width=True, 
            on_select="rerun", 
            selection_mode="single-row"
        )
        
        if not df_filtered.empty:
            try:
                selected_symbol = df_filtered.iloc[event.selection.rows[0]]["מניה"] if event and event.selection and event.selection.rows else df_filtered.iloc[0]["מניה"]
            except Exception:
                selected_symbol = df_filtered.iloc[0]["מניה"]
            
            if selected_symbol:
                st.markdown(f"### 🎯 ניתוח טכני ממוקד: **{selected_symbol}**")
                matched_row = next(item for item in results if item["מניה"] == selected_symbol)
                df_plot = matched_row["raw_data"]
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, 
                                    subplot_titles=("מחיר מניה (Candlestick)", "מדד זרימת נפח (OBV & SMA 14)"))
                
                fig.add_trace(gr.Candlestick(
                    x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], 
                    low=df_plot['Low'], close=df_plot['Close'], name='מחיר'
                ), row=1, col=1)
                
                fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV'], name='OBV', line=dict(color='#FFA500', width=2.5)), row=2, col=1)
                fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV_SMA'], name='OBV SMA', line=dict(color='#888888', width=1.5, dash='dash')), row=2, col=1)
                
                fig.update_layout(
                    height=550, showlegend=True, template="plotly_dark", xaxis_rangeslider_visible=False,
                    margin=dict(l=20, r=20, t=40, b=20)
                )
                st.plotly_chart(fig, use_container_width=True)
else:
    st.info("לחץ על כפתור 'הרץ ניתוח שוק, מפת עץ ומגמות סקטורים' למעלה כדי להתחיל.")
