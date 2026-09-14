import yfinance as yf
import pandas as pd
import datetime
import warnings
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Suppress warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=UserWarning)

CURRENT_DATE = datetime.date.today()
END_DATE = CURRENT_DATE.strftime("%Y-%m-%d")

TIME_CONFIGS = {
    "Daily": {"interval": "1d", "start_date": (CURRENT_DATE - pd.DateOffset(months=8)).strftime("%Y-%m-%d")},
    "Weekly": {"interval": "1wk", "start_date": (CURRENT_DATE - pd.DateOffset(years=2)).strftime("%Y-%m-%d")},
    "Monthly": {"interval": "1mo", "start_date": (CURRENT_DATE - pd.DateOffset(years=5)).strftime("%Y-%m-%d")}
}

nasdaq_100_tickers = [
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "ALAB", "ALNY", "AMAT",
    "AMD", "AMGN", "AMZN", "APP", "ARM", "ASML", "AVGO", "AXON", "BKR", "BKNG",
    "CDNS", "CEG", "CHTR", "CMCSA", "COST", "CPRT", "CRWD", "CSCO", "CSX", "CTAS",
    "CTSH", "DASH", "DDOG", "DXCM", "EXC", "FAST", "FTNT", "GEHC", "GILD", "GOOG",
    "GOOGL", "HON", "IDXX", "INTC", "INTU", "ISRG", "KDP", "KHC", "KLAC", "LITE",
    "LIN", "LRCX", "MAR", "MCHP", "MDLZ", "MELI", "META", "MNST", "MRVL", "MSFT",
    "MU", "NFLX", "NVDA", "NXPI", "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR",
    "PDD", "PEP", "PLTR", "QCOM", "REGN", "ROP", "ROST", "SBUX", "SNPS", "TEAM",
    "TMUS", "TSLA", "TTD", "TTWO", "TXN", "VRSK", "VRTX", "WBD", "WDAY", "XEL", "ZS"
]

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_current_td9_stage(df, direction='buy'):
    close = df['Close']
    n = len(close)
    if n < 5:
        return 0
        
    current_count = 0
    setup_active = False
    completed = False
    
    for i in range(4, n):
        if direction == 'buy':
            condition = close.iloc[i] < close.iloc[i-4]
        else:
            condition = close.iloc[i] > close.iloc[i-4]
        
        if condition:
            if completed:
                continue
            if not setup_active:
                setup_active = True
                current_count = 1
            else:
                current_count += 1
                if current_count == 9:
                    completed = True
        else:
            setup_active = False
            current_count = 0
            completed = False
            
    if completed:
        return 0
        
    return current_count

# Run Scanner for both Buy and Sell with RSI
all_scan_results = []
for tf_name, cfg in TIME_CONFIGS.items():
    for ticker in nasdaq_100_tickers:
        try:
            df = yf.download(ticker, start=cfg['start_date'], end=END_DATE, interval=cfg['interval'], progress=False, auto_adjust=True)
            if df.empty or len(df) < 20:  # Need at least 20 periods for reliable 14-period RSI
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            # Calculate RSI column
            df['RSI'] = calculate_rsi(df['Close'], period=14)
            latest_rsi = round(float(df['RSI'].iloc[-1]), 1) if not pd.isna(df['RSI'].iloc[-1]) else 0.0
                
            # Check Buy Setup
            buy_stage = get_current_td9_stage(df, direction='buy')
            if buy_stage in [6, 7, 8]:
                all_scan_results.append({
                    'Type': 'BUY',
                    'Timeframe': tf_name,
                    'Ticker': ticker,
                    'Current TD Stage': f"Stage {buy_stage}",
                    'Bars Away': 9 - buy_stage,
                    'RSI (14)': latest_rsi,
                    'Latest Close ($)': round(float(df['Close'].iloc[-1]), 2),
                    'As of Date': df.index[-1].strftime("%Y-%m-%d")
                })
                
            # Check Sell Setup
            sell_stage = get_current_td9_stage(df, direction='sell')
            if sell_stage in [6, 7, 8]:
                all_scan_results.append({
                    'Type': 'SELL',
                    'Timeframe': tf_name,
                    'Ticker': ticker,
                    'Current TD Stage': f"Stage {sell_stage}",
                    'Bars Away': 9 - sell_stage,
                    'RSI (14)': latest_rsi,
                    'Latest Close ($)': round(float(df['Close'].iloc[-1]), 2),
                    'As of Date': df.index[-1].strftime("%Y-%m-%d")
                })
        except Exception:
            pass

df_all = pd.DataFrame(all_scan_results)

# Build HTML Email Body
if not df_all.empty:
    df_all = df_all.sort_values(by=['Type', 'Timeframe', 'Current TD Stage'], ascending=[True, True, False]).reset_index(drop=True)
    html_table = df_all.to_html(index=False, classes='table', border=0)
    body_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; }}
            h3 {{ color: #111; }}
            table.table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
            table.table th {{ background-color: #f4f4f4; padding: 10px; border: 1px solid #ddd; text-align: left; }}
            table.table td {{ padding: 8px; border: 1px solid #ddd; text-align: left; }}
        </style>
    </head>
    <body>
        <h3>🚨 NASDAQ-100 TD9 & RSI MULTI-TIMEFRAME WATCHLIST (STAGES 6, 7, 8) — {CURRENT_DATE}</h3>
        {html_table}
    </body>
    </html>
    """
else:
    body_content = f"<p>No Nasdaq-100 stocks currently at Stage 6, 7, or 8 for Buy or Sell setups across Daily, Weekly, or Monthly as of {CURRENT_DATE}.</p>"

# Email Configuration
SENDER_EMAIL = os.environ.get("MAIL_USER")
RECEIVER_EMAIL = os.environ.get("MAIL_USER")
EMAIL_PASSWORD = os.environ.get("MAIL_PASS")

if not SENDER_EMAIL or not EMAIL_PASSWORD:
    raise ValueError("Missing MAIL_USER or MAIL_PASS environment variables.")

msg = MIMEMultipart()
msg['From'] = SENDER_EMAIL
msg['To'] = RECEIVER_EMAIL
msg['Subject'] = f"TD9 & RSI Watchlist Report - {CURRENT_DATE}"
msg.attach(MIMEText(body_content, 'html'))

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(SENDER_EMAIL, EMAIL_PASSWORD)
    server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    server.quit()
    print("Email sent successfully!")
except Exception as e:
    print(f"Failed to send email: {e}")
