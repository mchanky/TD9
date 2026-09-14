import yfinance as yf
import pandas as pd
import datetime
import warnings
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Suppress warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=UserWarning)

CURRENT_DATE = datetime.date.today()
END_DATE = CURRENT_DATE.strftime("%Y-%m-%d")

TIME_CONFIGS = {
    "Daily": {"interval": "1d", "start_date": (CURRENT_DATE - pd.DateOffset(months=8)).strftime("%Y-%m-%d")},
    "Weekly": {"interval": "1wk", "start_date": (CURRENT_DATE - pd.DateOffset(years=1, months=6)).strftime("%Y-%m-%d")},
    "Monthly": {"interval": "1mo", "start_date": (CURRENT_DATE - pd.DateOffset(years=2)).strftime("%Y-%m-%d")}
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

def get_current_td9_stage(df):
    close = df['Close']
    condition = close < close.shift(4)
    setup_count = 0
    for val in condition:
        if val:
            setup_count += 1
            if setup_count > 9:
                setup_count = 1 
        else:
            setup_count = 0
    return setup_count

# Run Scanner
all_scan_results = []
for tf_name, cfg in TIME_CONFIGS.items():
    for ticker in nasdaq_100_tickers:
        try:
            df = yf.download(ticker, start=cfg['start_date'], end=END_DATE, interval=cfg['interval'], progress=False, auto_adjust=True)
            if df.empty or len(df) < 15:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            current_stage = get_current_td9_stage(df)
            if current_stage in [6, 7, 8]:
                last_close = df['Close'].iloc[-1]
                last_date = df.index[-1].strftime("%Y-%m-%d")
                all_scan_results.append({
                    'Timeframe': tf_name,
                    'Ticker': ticker,
                    'Current TD Stage': f"Stage {current_stage}",
                    'Bars Away': 9 - current_stage,
                    'Latest Close ($)': round(float(last_close), 2),
                    'As of Date': last_date
                })
        except Exception:
            pass

df_all = pd.DataFrame(all_scan_results)

# Format Email Body
if not df_all.empty:
    df_all = df_all.sort_values(by=['Timeframe', 'Current TD Stage'], ascending=[True, False]).reset_index(drop=True)
    body_content = f"🚨 NASDAQ-100 TD9 BUY WATCHLIST (STAGES 6, 7, 8) — {CURRENT_DATE}\n\n" + df_all.to_string(index=False)
else:
    body_content = f"No Nasdaq-100 stocks currently at Stage 6, 7, or 8 across Daily, Weekly, or Monthly as of {CURRENT_DATE}."

# Email Configuration (We will use GitHub Secrets for safety)
import os
SENDER_EMAIL = os.environ.get("MAIL_USER")
RECEIVER_EMAIL = os.environ.get("MAIL_USER")
EMAIL_PASSWORD = os.environ.get("MAIL_PASS")

msg = MIMEMultipart()
msg['From'] = SENDER_EMAIL
msg['To'] = RECEIVER_EMAIL
msg['Subject'] = f"TD9 Watchlist Report - {CURRENT_DATE}"
msg.attach(MIMEText(body_content, 'plain'))

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(SENDER_EMAIL, EMAIL_PASSWORD)
    server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    server.quit()
    print("Email sent successfully!")
except Exception as e:
    print(f"Failed to send email: {e}")
