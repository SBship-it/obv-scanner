import pandas as pd
import yfinance as yf
import ta
import streamlit as st
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
import urllib.request
import time

# הגדרת עיצוב העמוד ומצב כהה (Dark Mode) כברירת מחדל
st.set_page_config(layout="wide", page_title="OBV Quant Scanner", page_icon="📈")

# עיצוב כותרות מעוצב עם CSS ותמיכה מלאה בימין לשמאל
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;700&display=swap');
    * { font-family: 'Assistant', sans-serif; }
    .main-title { font-size: 36px; font-weight: bold; color: #1E90FF; margin-bottom: 5px; text-align: right; direction: rtl; }
    .sub-title { font-size: 18px; color: #A0A0A0; margin-bottom: 25px; text-align: right; direction: rtl; }
    .stButton>button { background-color: #1E90FF; color: white; width: 100%; font-size: 16px; border-radius: 8px; font-weight: bold; }
    div[data-testid="stMarkdownContainer"] > p { text-align: right; direction: rtl; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📈 סורק שוק מלא: OBV Ultra Scanner</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">סריקה מלאה בזמן אמת של כל מניות ה-S&P 500 וה-Nasdaq 100 לזיהוי פריצות במדד זרימת הכסף (OBV)</div>', unsafe_allow_html=True)

# --- פונקציה להבאת רשימת כל הסימולים מוויקיפדיה (מעל 500 מניות) ---
@st.cache_data(ttl=86400)
def get_all_us_symbols():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    symbols = []
    
    # משיכת S&P 500
    try:
        req = urllib.request.Request('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
        with urllib.request.urlopen(req) as response:
            df_sp = pd.read_html(response.read())[0]
            sym_col = [col for col in df_sp.columns if 'symbol' in str(col).lower() or 'ticker' in str(col).lower()][0]
            symbols.extend(df_sp[sym_col].tolist())
    except Exception: pass

    # משיכת Nasdaq 100
    try:
        req = urllib.request.Request('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers)
        with urllib.request.urlopen(req) as response:
            html_tables = pd.read_html(response.read())
            for table in html_tables:
                if any('ticker' in str(col).lower() or 'symbol' in str(col).lower() or 'company' in str(col).lower() for col in table.columns):
                    sym_col = [col for col in table.columns if 'ticker' in str(col).lower() or 'symbol' in str(col).lower()]
                    if sym_col:
                        symbols.extend(table[sym_col[0]].tolist())
                        break
    except Exception: pass

    # ניקוי וסינון סימולים כפולים או לא תקינים
    clean_symbols = []
    for s in set(symbols):
        if isinstance(s, str) and len(s) < 6 and s.isalpha():
            clean_symbols.append(s.strip().upper().replace(".", "-"))
            
    if not clean_symbols:
        clean_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "NFLX", "INTC"]
        
    return sorted(clean_symbols)

symbols = get_all_us_symbols()

# הצגת כמות המניות הטעונות במערכת
st.write(f"📋 נטענו {len(symbols)} מניות מסנפ-500 ונאסדאק-100 המוכנות לסריקה.")

# כפתור הפעלה מעוצב
if st.button("🚀 הרץ סריקה מלאה על כל השוק (S&P 500 & Nasdaq 100)"):
    all_results = []
    
    # חלוקת המניות לקבוצות (בנצ'ים) של 30 מניות כדי לא להיחסם בענן
    chunk_size = 30
    symbol_chunks = [symbols[i:i + chunk_size] for i in range(0, len(symbols), chunk_size)]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with st.spinner("⚡ מנתח את כל מניות וול סטריט בצורה מבוזרת... אנא המתן"):
        for index, chunk in enumerate(symbol_chunks):
            status_text.markdown(f"🔄 סורק קבוצה {index + 1} מתוך {len(symbol_chunks)} ({len(chunk)} מניות)...")
            
            try:
                # הורדת נתונים לקבוצה הנוכחית
                data = yf.download(chunk, period="6mo", interval="1d", group_by='ticker', progress=False, auto_adjust=True)
                
                # זיהוי המניות בקבוצה שירדו בהצלחה
                downloaded_tickers = list(set([col[0] for col in data.columns])) if isinstance(data.columns, pd.MultiIndex) else chunk
                
                for symbol in downloaded_tickers:
                    try:
                        if isinstance(data.columns, pd.MultiIndex) and symbol not in data.columns.levels[0]: 
                            continue
                            
                        df = data[symbol].dropna().copy()
                        if len(df) < 30: continue
                        
                        # איתור דינמי של שמות העמודות
                        close_col = [c for c in df.columns if 'close' in c.lower()][0]
                        vol_col = [c for c in df.columns if 'volume' in c.lower()][0]
                        open_col = [c for c in df.columns if 'open' in c.lower()][0]
                        high_col = [c for c in df.columns if 'high' in c.lower()][0]
                        low_col = [c for c in df.columns if 'low' in c.lower()][0]
                        
                        close = df[close_col].squeeze()
                        volume = df[vol_col].squeeze()
                        
                        if close.iloc[-1] < 5: continue  # סינון מניות פני
                        
                        # חישוב OBV וממוצע נע 14
                        obv_series = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
                        obv_sma = obv_series.rolling(14).mean()
                        
                        df["OBV"] = obv_series
                        df["OBV_SMA"] = obv_sma
                        
                        if obv_series.iloc[-1] > obv_sma.iloc[-1]:
                            above_series = obv_series > obv_sma
                            consecutive_days = 0
                            for val in reversed(above_series):
                                if val: consecutive_days += 1
                                else: break
                            
                            pct_change_since_cross = 0.0
                            if consecutive_days > 0 and consecutive_days < len(df):
                                cross_day_price = close.iloc[-consecutive_days]
                                pct_change_since_cross = ((close.iloc[-1] - cross_day_price) / cross_day_price) * 100
                            
                            all_results.append({
                                "מניה": symbol,
                                "מחיר אחרון ($)": round(close.iloc[-1], 2),
                                "ימים מעל ממוצע": consecutive_days,
                                "שינוי מאז החצייה (%)": round(pct_change_since_cross, 2),
                                "מחזור מסחר (Volume)": int(volume.iloc[-1]),
                                "raw_data": df[[open_col, high_col, low_col, close_col, "OBV", "OBV_SMA"]]
                            })
                    except Exception: continue
            except Exception: pass
            
            # עדכון מד התקדמות והשהיה קלה למניעת חסימות
            progress_bar.progress((index + 1) / len(symbol_chunks))
            time.sleep(0.4) 
            
        status_text.markdown("✅ הסריקה הסתיימה בהצלחה!")
        st.session_state['scan_open_results'] = all_results

# הצגת התוצאות והגרפים האינטראקטיביים
if 'scan_open_results' in st.session_state:
    results = st.session_state['scan_open_results']
    
    if results:
        df_res = pd.DataFrame(results).sort_values(by="ימים מעל ממוצע", ascending=False)
        display_cols = ["מניה", "מחיר אחרון ($)", "ימים מעל ממוצע", "שינוי מאז החצייה (%)", "מחזור מסחר (Volume)"]
        
        st.markdown(f"### 📊 מניות שנמצאו ({len(df_res)} מניות מתוך כל השוק)")
        st.caption("לחץ על שורה כלשהי בטבלה כדי לטעון ולהציג את הגרף הטכני המלא שלה למטה.")
        
        # טבלה אינטראקטיבית
        event = st.dataframe(
            df_res[display_cols].set_index("מניה"), 
            use_container_width=True, 
            on_select="rerun", 
            selection_mode="single-row"
        )
        
        # בחירת המניה להצגה (ברירת מחדל היא הראשונה בטבלה)
        try:
            selected_symbol = df_res.iloc[event.selection.rows[0]]["מניה"] if event and event.selection and event.selection.rows else df_res.iloc[0]["מניה"]
        except:
            selected_symbol = df_res.iloc[0]["מניה"] if len(df_res) > 0 else None
        
        if selected_symbol:
            st.markdown(f"### 🎯 ניתוח טכני אינטראקטיבי: **{selected_symbol}**")
            matched_row = next(item for item in results if item["מניה"] == selected_symbol)
            df_plot = matched_row["raw_data"]
            
            c_col = [c for c in df_plot.columns if 'close' in c.lower()][0]
            o_col = [c for c in df_plot.columns if 'open' in c.lower()][0]
            h_col = [c for c in df_plot.columns if 'high' in c.lower()][0]
            l_col = [c for c in df_plot.columns if 'low' in c.lower()][0]
            
            # יצירת גרף מפוצל מקצועי
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, 
                                subplot_titles=("מחיר מניה (Candlestick)", "מדד זרימת נפח (OBV & SMA 14)"))
            
            # 1. גרף נרות יפניים (מחיר)
            fig.add_trace(gr.Candlestick(
                x=df_plot.index, open=df_plot[o_col], high=df_plot[h_col], 
                low=df_plot[l_col], close=df_plot[c_col], name='מחיר המניה'
            ), row=1, col=1)
            
            # 2. גרף אינדיקטור OBV
            fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV'], name='OBV', line=dict(color='#FFA500', width=2.5)), row=2, col=1)
            fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV_SMA'], name='OBV SMA 14', line=dict(color='#888888', width=1.5, dash='dash')), row=2, col=1)
            
            fig.update_layout(
                height=650, 
                showlegend=True, 
                template="plotly_dark", 
                xaxis_rangeslider_visible=False,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("לא נמצאו מניות העונות על תנאי הסינון ברגע זה.")
else:
    st.info("לחץ על כפתור 'הרץ סריקה מלאה' למעלה כדי להתחיל את הסריקה על פני כל השוק.")
