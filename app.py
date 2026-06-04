import pandas as pd
import yfinance as yf
import ta
import streamlit as st
import plotly.graph_objects as gr
from plotly.subplots import make_subplots

# הגדרת מבנה העמוד בדפדפן
st.set_page_config(layout="wide", page_title="OBV Quant Scanner", page_icon="📈")
st.title("📈 OBV Market Scanner & Analytics")
st.subheader("Real-time OBV Breakout Scanner for Market Leaders")

# --- פונקציה שמחזירה את המניות המובילות ביותר (חסין חסימות שרת) ---
@st.cache_data(ttl=86400)
def get_us_symbols():
    return [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "NFLX", "INTC",
        "MS", "GS", "JPM", "BAC", "WMT", "COST", "DIS", "NKE", "XOM", "CVX", 
        "LLY", "UNH", "JNJ", "V", "MA", "AVGO", "ORCL", "ADBE", "CRM", "QCOM",
        "TXN", "MU", "AMAT", "LRCX", "PANW", "FTNT", "NOW", "PLTR", "SMCI", "UBER"
    ]

# --- פונקציה להורדת נתוני מסחר ---
@st.cache_data(ttl=3600)
def load_scanner_data(symbols):
    df = yf.download(symbols, period='6mo', interval='1d', group_by='ticker', progress=False, auto_adjust=True)
    return df

symbols = get_us_symbols()

# כפתור הפעלה
if st.button('🚀 Run Live Market Scanner'):
    with st.spinner('⚡ Downloading and analyzing market data... Please wait'):
        data = load_scanner_data(symbols)
        all_results = []
        
        # זיהוי המניות שירדו בהצלחה מהשרת
        downloaded_tickers = list(set([col[0] for col in data.columns])) if isinstance(data.columns, pd.MultiIndex) else symbols
        
        for symbol in downloaded_tickers:
            try:
                if symbol not in data.columns.levels[0] if isinstance(data.columns, pd.MultiIndex) else [symbol]: 
                    continue
                    
                df = data[symbol].dropna().copy()
                if len(df) < 30: continue
                
                # איתור דינמי של שמות העמודות (למניעת שגיאות פורמט)
                close_col = [c for c in df.columns if 'close' in c.lower()][0]
                vol_col = [c for c in df.columns if 'volume' in c.lower()][0]
                open_col = [c for c in df.columns if 'open' in c.lower()][0]
                high_col = [c for c in df.columns if 'high' in c.lower()][0]
                low_col = [c for c in df.columns if 'low' in c.lower()][0]
                
                close = df[close_col].squeeze()
                volume = df[vol_col].squeeze()
                
                # סינון מניות מתחת ל-5 דולר
                if close.iloc[-1] < 5: continue 
                
                # חישוב אינדיקטור OBV וממוצע נע 14 שלו
                obv_series = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
                obv_sma = obv_series.rolling(14).mean()
                
                df['OBV'] = obv_series
                df['OBV_SMA'] = obv_sma
                
                # בדיקה האם ה-OBV נמצא כרגע מעל הממוצע
                if obv_series.iloc[-1] > obv_sma.iloc[-1]:
                    above_series = obv_series > obv_sma
                    consecutive_days = 0
                    for val in reversed(above_series):
                        if val: consecutive_days += 1
                        else: break
                    
                    # חישוב שינוי המחיר באחוזים מאז יום החצייה
                    pct_change_since_cross = 0.0
                    if consecutive_days > 0 and consecutive_days < len(df):
                        cross_day_price = close.iloc[-consecutive_days]
                        pct_change_since_cross = ((close.iloc[-1] - cross_day_price) / cross_day_price) * 100
                    
                    all_results.append({
                        'Symbol': symbol, 
                        'Price ($)': round(close.iloc[-1], 2), 
                        'Days Above SMA': consecutive_days,
                        'Change Since Cross (%)': round(pct_change_since_cross, 2), 
                        'Volume': int(volume.iloc[-1]), 
                        'raw_data': df[[open_col, high_col, low_col, close_col, 'OBV', 'OBV_SMA']]
                    })
            except Exception: continue
            
        st.session_state['scan_open_results'] = all_results

# הצגת התוצאות והגרפים
if 'scan_open_results' in st.session_state:
    results = st.session_state['scan_open_results']
    if results:
        df_res = pd.DataFrame(results).sort_values(by='Days Above SMA', ascending=False)
        display_cols = ['Symbol', 'Price ($)', 'Days Above SMA', 'Change Since Cross (%)', 'Volume']
        
        st.markdown("### 📊 Found Stocks")
        st.caption("Click on any row in the table to display its technical chart below.")
        
        # טבלה אינטראקטיבית לבחירת מניה
        event = st.dataframe(df_res[display_cols].set_index('Symbol'), use_container_width=True, on_select='rerun', selection_mode='single-row')
        
        try:
            selected_symbol = df_res.iloc[event.selection.rows[0]]['Symbol'] if event and event.selection and event.selection.rows else df_res.iloc[0]['Symbol']
        except:
            selected_symbol = df_res.iloc[0]['Symbol'] if len(df_res) > 0 else None
            
        if selected_symbol:
            st.markdown(f"### 🎯 Technical Analysis: **{selected_symbol}**")
            matched_row = next(item for item in results if item['Symbol'] == selected_symbol)
            df_plot = matched_row['raw_data']
            
            c_col = [c for c in df_plot.columns if 'close' in c.lower()][0]
            o_col = [c for c in df_plot.columns if 'open' in c.lower()][0]
            h_col = [c for c in df_plot.columns if 'high' in c.lower()][0]
            l_col = [c for c in df_plot.columns if 'low' in c.lower()][0]
            
            # בניית גרף מפוצל: נרות למעלה, OBV למטה
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=('Price (Candlestick)', 'OBV & SMA 14'))
            fig.add_trace(gr.Candlestick(x=df_plot.index, open=df_plot[o_col], high=df_plot[h_col], low=df_plot[l_col], close=df_plot[c_col], name='Price'), row=1, col=1)
            fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV'], name='OBV', line=dict(color='#00D2FF', width=2.5)), row=2, col=1)
            fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV_SMA'], name='SMA 14', line=dict(color='#FF416C', width=1.5, dash='dash')), row=2, col=1)
            
            fig.update_layout(height=700, showlegend=True, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
    else: 
        st.info('No stocks matched the criteria at this moment.')
else: 
    st.info('System Ready! Click the button above to start scanning.')
