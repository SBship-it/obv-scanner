import pandas as pd
import yfinance as yf
import ta
import streamlit as st
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
import urllib.request

# הגדרת עיצוב העמוד ומצב כהה (Dark Mode) כברירת מחדל
st.set_page_config(layout="wide", page_title="OBV Quant Scanner", page_icon="📈")

# עיצוב כותרות מעוצב עם CSS
st.markdown("""
    <style>
    .main-title { font-size: 36px; font-weight: bold; color: #1E90FF; margin-bottom: 5px; text-align: right; }
    .sub-title { font-size: 18px; color: #A0A0A0; margin-bottom: 25px; text-align: right; }
    .stButton>button { background-color: #1E90FF; color: white; width: 100%; font-size: 16px; border-radius: 8px; }
    div[data-testid="stMarkdownContainer"] > p { text-align: right; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📈 סורק מניות ומערכת OBV Ultra</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">מעקב בזמן אמת אחר זרימת כסף (Volume) ומניות שחוצות את ממוצע ה-OBV ב-S&P 500 ו-Nasdaq 100</div>', unsafe_allow_html=True)

# --- פונקציה להבאת רשימת סימולים מוויקיפדיה ---
@st.cache_data(ttl=86400)
def get_us_symbols():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    symbols = []
    
    # S&P 500
    try:
        req = urllib.request.Request('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
        with urllib.request.urlopen(req) as response:
            df_sp = pd.read_html(response.read())[0]
            sym_col = [col for col in df_sp.columns if 'symbol' in str(col).lower() or 'ticker' in str(col).lower()][0]
            symbols.extend(df_sp[sym_col].tolist())
    except Exception:
        pass

    # Nasdaq 100
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
    except Exception:
        pass

    clean_symbols = []
    for s in set(symbols):
        if isinstance(s, str) and len(s) < 6 and s.isalpha():
            clean_symbols.append(s.strip().upper().replace(".", "-"))
            
    if not clean_symbols:
        clean_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "NFLX", "INTC"]
        
    return sorted(clean_symbols)

# --- פונקציה להורדת נתוני מסחר ---
@st.cache_data(ttl=3600)
def load_scanner_data(symbols):
    return yf.download(symbols, period="6mo", interval="1d", group_by='ticker', progress=False, auto_adjust=True)

symbols = get_us_symbols()

# כפתור הפעלה מעוצב
if st.button("🚀 הרץ סורק שוק בזמן אמת"):
    with st.spinner("⚡ מוריד ומנתח נתוני שוק ברגע זה... אנא המתן"):
        data = load_scanner_data(symbols)
        all_results = []
        
        for symbol in symbols:
            try:
                if symbol not in data.columns.levels[0]: continue
                df = data[symbol].dropna().copy()
                if len(df) < 30: continue
                
                close = df["Close"].squeeze()
                volume = df["Volume"].squeeze()
                
                # חישוב אינדיקטורים
                obv_series = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
                obv_sma = obv_series.rolling(14).mean()
                
                df["OBV"] = obv_series
                df["OBV_SMA"] = obv_sma
                
                is_above_now = obv_series.iloc[-1] > obv_sma.iloc[-1]
                
                if is_above_now:
                    above_series = obv_series > obv_sma
                    consecutive_days = 0
                    for val in reversed(above_series):
                        if val: consecutive_days += 1
                        else: break
                    
                    pct_change_since_cross = 0.0
                    if consecutive_days > 0 and consecutive_days < len(df):
                        cross_day_price = close.iloc[-consecutive_days]
                        pct_change_since_cross = ((close.iloc[-1] - cross_day_price) / cross_day_price) * 100
                    
                    if close.iloc[-1] < 5: continue  # סינון מניות פני

                    all_results.append({
                        "מניה": symbol,
                        "מחיר אחרון ($)": round(close.iloc[-1], 2),
                        "ימים מעל ממוצע": consecutive_days,
                        "שינוי מאז החצייה (%)": round(pct_change_since_cross, 2),
                        "מחזור מסחר (Volume)": int(volume.iloc[-1]),
                        "raw_data": df 
                    })
            except Exception:
                continue
                
        st.session_state['scan_open_results'] = all_results

# הצגת התוצאות והגרפים
if 'scan_open_results' in st.session_state:
    results = st.session_state['scan_open_results']
    
    if results:
        df_res = pd.DataFrame(results)
        display_cols = ["מניה", "מחיר אחרון ($)", "ימים מעל ממוצע", "שינוי מאז החצייה (%)", "מחזור מסחר (Volume)"]
        
        st.markdown("### 📊 מניות שנמצאו (לחץ על שורה בטבלה כדי להציג את הגרף שלה)")
        
        # טבלה אינטראקטיבית המאפשרת בחירת שורה
        event = st.dataframe(
            df_res[display_cols].set_index("מניה"), 
            use_container_width=True, 
            on_select="rerun", 
            selection_mode="single-row"
        )
        
        # בחירת המניה להצגה (ברירת מחדל היא הראשונה בטבלה)
        selected_symbol = df_res.iloc[event.selection.rows[0]]["מניה"] if event and event.selection and event.selection.rows else df_res.iloc[0]["מניה"]
        
        if selected_symbol:
            st.markdown(f"### 🎯 ניתוח טכני אינטראקטיבי: **{selected_symbol}**")
            matched_row = next(item for item in results if item["מניה"] == selected_symbol)
            df_plot = matched_row["raw_data"]
            
            # יצירת גרף מפוצל מקצועי
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, 
                                subplot_titles=("מחיר מניה (Candlestick)", "מדד זרימת נפח (OBV & SMA 14)"))
            
            # 1. גרף נרות יפניים (מחיר)
            fig.add_trace(gr.Candlestick(
                x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], 
                low=df_plot['Low'], close=df_plot['Close'], name='מחיר המניה'
            ), row=1, col=1)
            
            # 2. גרף אינדיקטור OBV
            fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV'], name='OBV', line=dict(color='#FFA500', width=2.5)), row=2, col=1)
            fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV_SMA'], name='OBV SMA 14', line=dict(color='#888888', width=1.5, dash='dash')), row=2, col=1)
            
            # הגדרות מראה ועיצוב כהה לגרף
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
    st.info("לחץ על כפתור 'הרץ סורק שוק בזמן אמת' למעלה כדי להתחיל את הסריקה.")
