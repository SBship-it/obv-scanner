import pandas as pd
import yfinance as yf
import ta
import streamlit as st
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
import urllib.request

st.set_page_config(layout="wide", page_title="OBV Quant Scanner", page_icon="📈")
st.title("📈 OBV Market Scanner & Analytics")
st.subheader("Real-time OBV Breakout Scanner for S&P 500 & Nasdaq 100")

@st.cache_data(ttl=86400)
def get_us_symbols():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    symbols = []
    try:
        req = urllib.request.Request('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
        with urllib.request.urlopen(req) as response:
            df_sp = pd.read_html(response.read())[0]
            sym_col = [col for col in df_sp.columns if 'symbol' in str(col).lower() or 'ticker' in str(col).lower()][0]
            symbols.extend(df_sp[sym_col].tolist())
    except Exception: pass
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
    clean_symbols = []
    for s in set(symbols):
        if isinstance(s, str) and len(s) < 6 and s.isalpha():
            clean_symbols.append(s.strip().upper().replace('.', '-'))
    if not clean_symbols:
        clean_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'NFLX', 'INTC']
    return sorted(clean_symbols)

@st.cache_data(ttl=3600)
def load_scanner_data(symbols):
    return yf.download(symbols, period='6mo', interval='1d', group_by='ticker', progress=False, auto_adjust=True)

symbols = get_us_symbols()

if st.button('🚀 Run Live Market Scanner'):
    with st.spinner('⚡ Downloading and analyzing market data... Please wait'):
        data = load_scanner_data(symbols)
        all_results = []
        for symbol in symbols:
            try:
                if symbol not in data.columns.levels[0]: continue
                df = data[symbol].dropna().copy()
                if len(df) < 30: continue
                close = df['Close'].squeeze()
                volume = df['Volume'].squeeze()
                obv_series = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
                obv_sma = obv_series.rolling(14).mean()
                df['OBV'] = obv_series
                df['OBV_SMA'] = obv_sma
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
                    if close.iloc[-1] < 5: continue
                    all_results.append({
                        'Symbol': symbol, 'Price ($)': round(close.iloc[-1], 2), 'Days Above SMA': consecutive_days,
                        'Change Since Cross (%)': round(pct_change_since_cross, 2), 'Volume': int(volume.iloc[-1]), 'raw_data': df
                    })
            except Exception: continue
        st.session_state['scan_open_results'] = all_results

if 'scan_open_results' in st.session_state:
    results = st.session_state['scan_open_results']
    if results:
        df_res = pd.DataFrame(results).sort_values(by='Days Above SMA', ascending=False)
        display_cols = ['Symbol', 'Price ($)', 'Days Above SMA', 'Change Since Cross (%)', 'Volume']
        st.markdown('### 📊 Found Stocks')
        st.caption('Click on any row to load and display its technical chart below.')
        event = st.dataframe(df_res[display_cols].set_index('Symbol'), use_container_width=True, on_select='rerun', selection_mode='single-row')
        
        # Safe selection fallback
        try:
            selected_symbol = df_res.iloc[event.selection.rows[0]]['Symbol'] if event and event.selection and event.selection.rows else df_res.iloc[0]['Symbol']
        except:
            selected_symbol = df_res.iloc[0]['Symbol']
            
        if selected_symbol:
            st.markdown(f'### 🎯 Technical Analysis: **{selected_symbol}**')
            matched_row = next(item for item in results if item['Symbol'] == selected_symbol)
            df_plot = matched_row['raw_data']
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=('Price (Candlestick)', 'OBV & SMA 14'))
            fig.add_trace(gr.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name='Price'), row=1, col=1)
            fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV'], name='OBV', line=dict(color='#00D2FF', width=2.5)), row=2, col=1)
            fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['OBV_SMA'], name='SMA 14', line=dict(color='#FF416C', width=1.5, dash='dash')), row=2, col=1)
            fig.update_layout(height=700, showlegend=True, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
    else: st.info('No stocks matched the criteria.')
else: st.info('System Ready! Click the button above to start scanning.')
