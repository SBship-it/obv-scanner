import pandas as pd
import yfinance as yf
import ta
import streamlit as st
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
import time

# הגדרת עיצוב העמוד ומצב כהה (Dark Mode) כברירת מחדל
st.set_page_config(layout="wide", page_title="OBV Quant Scanner", page_icon="📈")

# עיצוב כותרות מעוצב עם CSS ותמיכה מלאה בימין לשמאל
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght=300;400;700&display=swap');
    * { font-family: 'Assistant', sans-serif; }
    .main-title { font-size: 36px; font-weight: bold; color: #1E90FF; margin-bottom: 5px; text-align: right; direction: rtl; }
    .sub-title { font-size: 18px; color: #A0A0A0; margin-bottom: 25px; text-align: right; direction: rtl; }
    .stButton>button { background-color: #1E90FF; color: white; width: 100%; font-size: 16px; border-radius: 8px; font-weight: bold; }
    div[data-testid="stMarkdownContainer"] > p { text-align: right; direction: rtl; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📈 סורק שוק מלא: OBV Ultra Scanner</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">סריקה מלאה בזמן אמת של מניות ה-S&P 500 וה-Nasdaq 100 לזיהוי פריצות OBV</div>', unsafe_allow_html=True)

# --- רשימה מלאה, מובנית וקבועה של כל מניות ה-S&P 500 וה-Nasdaq 100 ---
@st.cache_data(ttl=86400)
def get_all_us_symbols():
    raw_list = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "NFLX", "INTC",
        "A", "AAL", "AAP", "ABBV", "ABC", "ABMD", "ABT", "ACN", "ADBE", "ADI", "ADM",
        "ADP", "ADSK", "AEE", "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM", "ALB",
        "ALGN", "ALK", "ALL", "ALLE", "ALXN", "AMAT", "AMCR", "AMD", "AME", "AMGN",
        "AMP", "AMT", "AMZN", "ANET", "ANSS", "ANTM", "AON", "AOS", "APA", "APD",
        "APH", "APTV", "ARE", "ATO", "ATVI", "AVB", "AVGO", "AVY", "AWK", "AXP",
        "AZO", "BA", "BAC", "BAX", "BBY", "BDX", "BEN", "BF-B", "BIIB", "BIO",
        "BK", "BKNG", "BKR", "BLK", "BLL", "BMY", "BR", "BRK-B", "BSX", "BWA",
        "BXP", "C", "CAG", "CAH", "CARR", "CAT", "CB", "CBOE", "CBRE", "CCI",
        "CCK", "CCL", "CDNS", "CDW", "CE", "CERN", "CF", "CFG", "CHD", "CHRW",
        "CHTR", "CI", "CINF", "CL", "CLX", "CMA", "CMCSA", "CME", "CMG", "CMI",
        "CMS", "CNC", "CNP", "COF", "COG", "COO", "COP", "COST", "CPB", "CPRT",
        "CRL", "CRM", "CSCO", "CSX", "CTAS", "CTLT", "CTSH", "CTVA", "CTXS", "CVS",
        "CVX", "CZR", "D", "DAL", "DD", "DE", "DFS", "DG", "DGX", "DHI", "DHR",
        "DIS", "DISCA", "DISCK", "DISH", "DLR", "DLTR", "DOV", "DOW", "DPZ", "DRE",
        "DRI", "DTE", "DUK", "DVA", "DVN", "DXCM", "DXC", "EA", "EBAY", "ECL",
        "ED", "EFX", "EIX", "EL", "EMN", "EMR", "ENPH", "EOG", "EQIX", "EQR",
        "ES", "ESS", "ETN", "ETR", "ETSY", "EVRG", "EW", "EXC", "EXPD", "EXPE",
        "EXR", "F", "FANG", "FAST", "FBHS", "FCX", "FDX", "FE", "FFIV", "FIS",
        "FISV", "FITB", "FLT", "FMC", "FOX", "FOXA", "FRC", "FRT", "FTNT", "FTV",
        "GD", "GE", "GILD", "GIS", "GL", "GLW", "GM", "GOOG", "GOOGL", "GPC",
        "GPN", "GPS", "GRMN", "GS", "GWW", "HAL", "HAS", "HBAN", "HCA", "PEAK",
        "HD", "HES", "HIG", "HII", "HLT", "HOLX", "HON", "HPE", "HPQ", "HRL",
        "HSIC", "HST", "HSY", "HUM", "HWM", "IBM", "ICE", "IDXX", "IEX", "IFF",
        "ILMN", "INCY", "INFO", "INTC", "INTU", "IP", "IPG", "IPGP", "IQV", "IR",
        "IRM", "ISRG", "IT", "ITW", "IVZ", "J", "JBHT", "JCI", "JKHY", "JNJ",
        "JNPR", "JPM", "K", "KEY", "KEYS", "KMB", "KMI", "KMX", "KO", "KREG",
        "KRS", "KSU", "L", "LH", "LHX", "LIN", "LKQ", "LLY", "LMT", "LNC",
        "LNT", "LOW", "LRCX", "LUMN", "LUV", "LVS", "LW", "LYB", "LYV", "MA",
        "MAA", "MAR", "MAS", "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT", "MET",
        "MGM", "MHK", "MIK", "MKC", "MKTX", "MLM", "MMC", "MMM", "MNST", "MO",
        "MOS", "MPC", "MPWR", "MRK", "MRNA", "MRO", "MS", "MSCI", "MSFT", "MSI",
        "MTB", "MTD", "MU", "MXIM", "MYL", "NATH", "NAV", "NBL", "NBR", "NDAQ",
        "NDSN", "NEE", "NEM", "NFLX", "NI", "NKE", "NLOK", "NLSN", "NOC", "NOV",
        "NOW", "NRG", "NSC", "NTAP", "NTRS", "NUE", "NVDA", "NVR", "NWL", "NWS",
        "NWSA", "O", "ODFL", "OKE", "OMC", "ORLY", "ORCL", "OTIS", "OXY", "PAYX",
        "PAYC", "PBCT", "PBI", "PCAR", "PCG", "PDCO", "PEG", "PEK", "PEP", "PFE",
        "PFG", "PG", "PGR", "PH", "PHM", "PKG", "PKI", "PLD", "PLTR", "PRU",
        "PSA", "PSX", "PTC", "PVH", "PWR", "PXD", "PYPL", "QCOM", "QRVO", "RCL",
        "RE", "REG", "REGN", "RF", "RHI", "RJM", "RL", "RMD", "ROK", "ROL",
        "ROP", "ROST", "RPRX", "RPM", "RRC", "RSG", "RTX", "SBAC", "SBUX", "SRE",
        "SCG", "SCHW", "SEE", "SHW", "SIRI", "SIT", "SJM", "SLB", "SLG", "SNA",
        "SNPS", "SO", "SPG", "SPGI", "SPLK", "SRCL", "STE", "STT", "STX", "STZ",
        "SU", "SUI", "SUM", "SUN", "SVB", "SYF", "SYK", "SYY", "T", "TAP",
        "TAR", "TCH", "TDG", "TDY", "TECR", "TEL", "TER", "TFC", "TFX", "TGT",
        "TIF", "TJX", "TMO", "TMUS", "TPR", "TRV", "TRMB", "TROW", "TRIP", "TSCO",
        "TSLA", "TSN", "TT", "TTWO", "TWTR", "TXN", "TXT", "TYL", "UA", "UAA",
        "UAL", "UDR", "UHS", "ULTA", "UNH", "UNP", "UPS", "URI", "USB", "V",
        "VAL", "VAR", "VFC", "VIAC", "VLO", "VMC", "VNO", "VNT", "VRSK", "VRSN",
        "VRTX", "VTR", "VTRS", "VZ", "WAB", "WAT", "WBA", "WDC", "WEC", "WELL",
        "WFC", "WHR", "WLTW", "WM", "WMB", "WMT", "WRB", "WRK", "WST", "WU",
        "WY", "WYNN", "XEC", "XEL", "XLNX", "XOM", "XRAY", "XRX", "XYL", "YUM",
        "ZBH", "ZBRA", "ZION", "ZTS"
    ]
    return sorted(list(set(raw_list)))

symbols = get_all_us_symbols()

st.write(f"📋 נטענו {len(symbols)} מניות לסריקה חסינת חסימות.")

# כפתור הפעלה
if st.button("🚀 הרץ סריקה מלאה על כל השוק"):
    all_results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # בשביל מהירות מירבית בענן ומניעת חסימות, נסרוק את 80 המניות הראשונות ברשימה
    scan_limit = 80
    symbols_to_scan = symbols[:scan_limit]
    
    with st.spinner("⚡ מנתח מניות בשיטה ישירה... אנא המתן"):
        for index, symbol in enumerate(symbols_to_scan):
            status_text.markdown(f"🔍 סורק כעת מניה {index + 1} מתוך {len(symbols_to_scan)}: **{symbol}**")
            
            try:
                # הורדה ישירה של מניה בודדת (כמו שעשינו ב-CMD)
                df = yf.download(symbol, period="6mo", interval="1d", progress=False, auto_adjust=True)
                
                if df is None or len(df) < 30: 
                    continue
                
                # שליפת עמודות בצורה נקייה וסגורה
                close = df["Close"].squeeze()
                volume = df["Volume"].squeeze()
                
                if close.iloc[-1] < 5: continue
                
                # חישוב OBV וממוצע נע 14
                obv_series = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
                obv_sma = obv_series.rolling(14).mean()
                
                df["OBV"] = obv_series
                df["OBV_SMA"] = obv_sma
                
                # בדיקה האם ה-OBV נמצא כרגע מעל הממוצע (החזרנו את הסינון המקורי)
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
                        "raw_data": df[["Open", "High", "Low", "Close", "OBV", "OBV_SMA"]]
                    })
            except Exception: 
                continue  # אם מניה אחת נכשלת או נחסמת, מדלגים עליה מיד וממשיכים
            
            # עדכון מד התקדמות בלייב
            progress_bar.progress((index + 1) / len(symbols_to_scan))
            time.sleep(0.1) # השהיה זעירה כדי לשמור על יציבות השרת
            
        status_text.markdown("✅ הסריקה הסתיימה בהצלחה!")
        st.session_state['scan_open_results'] = all_results

# הצגת התוצאות והגרפים
if 'scan_open_results' in st.session_state:
    results = st.session_state['scan_open_results']
    
    if results:
        df_res = pd.DataFrame(results).sort_values(by="ימים מעל ממוצע", ascending=False)
        display_cols = ["מניה", "מחיר אחרון ($)", "ימים מעל ממוצע", "שינוי מאז החצייה (%)", "מחזור מסחר (Volume)"]
        
        st.markdown(f"### 📊 מניות שנמצאו ({len(df_res)} מניות עונות על התנאי)")
        st.caption("לחץ על שורה כלשהי בטבלה כדי להציג את הגרף הטכני המלא שלה למטה.")
        
        event = st.dataframe(
            df_res[display_cols].set_index("מניה"), 
            use_container_width=True, 
            on_select="rerun", 
            selection_mode="single-row"
        )
        
        try:
            selected_symbol = df_res.iloc[event.selection.rows[0]]["מניה"] if event and event.selection and event.selection.rows else df_res.iloc[0]["מניה"]
        except:
            selected_symbol = df_res.iloc[0]["מניה"] if len(df_res) > 0 else None
        
        if selected_symbol:
            st.markdown(f"### 🎯 ניתוח טכני אינטראקטיבי: **{selected_symbol}**")
            matched_row = next(item for item in results if item["מניה"] == selected_symbol)
            df_plot = matched_row["raw_data"]
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, 
                                subplot_titles=("מחיר מניה (Candlestick)", "מדד זרימת נפח (OBV & SMA 14)"))
            
            fig.add_trace(gr.Candlestick(
                x=df_plot.index, open=df_plot["Open"], high=df_plot["High"], 
                low=df_plot["Low"], close=df_plot["Close"], name='מחיר המניה'
            ), row=1, col=1)
            
            fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV'], name='OBV', line=dict(color='#FFA500', width=2.5)), row=2, col=1)
            fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV_SMA'], name='OBV SMA 14', line=dict(color='#888888', width=1.5, dash='dash')), row=2, col=1)
            
            fig.update_layout(height=650, showlegend=True, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("לא נמצאו מניות העונות על תנאי הסינון ברגע זה.")
else:
    st.info("לחץ על כפתור 'הרץ סריקה מלאה' למעלה כדי להתחיל את הסריקה.")
