"""
services/notifications.py — Notification & Alerting Engine for Telegram
Handles sending real-time alerts to the user's mobile device.
"""
import requests
import os

def send_telegram_message(token, chat_id, message):
    """
    Sends a message via the Telegram Bot API.
    """
    if not token or not chat_id:
        return False, "Token/ChatID not configured."
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True, "Message sent."
        return False, f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

def format_trade_alert(ticker, action, price, pnl=None):
    """
    Formats a trade alert for Telegram.
    """
    icon = "🚀" if action.upper() == "BUY" else "📉"
    msg = f"{icon} *QUANTUM TRADE ALERT*\n\n"
    msg += f"*Ticker:* {ticker}\n"
    msg += f"*Acción:* {action.upper()}\n"
    msg += f"*Precio:* ${price:,.2f}\n"
    if pnl is not None:
        msg += f"*P&L Result:* ${pnl:+,.2f}\n"
    msg += "\n_Quantum Retail Terminal v7.0_"
    return msg

def format_risk_alert(ticker, corr_value):
    """
    Formats a risk correlation alert.
    """
    msg = f"⚠️ *QUANTUM RISK ALERT*\n\n"
    msg += f"Asset: *{ticker}*\n"
    msg += f"Status: *HIGH CORRELATION* ({corr_value:.2f})\n"
    msg += f"Note: Your portfolio is over-exposed to systematic risk in this asset's group."
    return msg
