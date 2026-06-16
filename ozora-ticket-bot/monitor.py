#!/usr/bin/env python3
"""
Ozora Ticket Bot
----------------
Checks the Ozora "Find ForSale" page, reads the current discount offer,
and sends you an alert (Telegram and/or WhatsApp via Twilio) when the
discount is at least EUR_THRESHOLD euros.

All settings come from environment variables (you set them once as
"secrets" in GitHub, no code editing needed):

  EUR_THRESHOLD        Minimum discount (in EUR) that triggers an alert. Default: 90

  -- Telegram (the easy option) --
  TELEGRAM_BOT_TOKEN   Token from @BotFather
  TELEGRAM_CHAT_ID     Your chat id

  -- WhatsApp via Twilio (optional) --
  TWILIO_ACCOUNT_SID   From your Twilio console
  TWILIO_AUTH_TOKEN    From your Twilio console
  TWILIO_FROM          e.g. whatsapp:+14155238886  (Twilio sandbox number)
  TWILIO_TO            e.g. whatsapp:+9725XXXXXXXX  (your WhatsApp number)

If a channel's variables are not set, that channel is simply skipped.
"""

import os
import re
import sys
import requests

PAGE_URL = "https://ticket.ozorafestival.eu/find-forsale?target_status=partpaid-for-sale"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36"
}


def fetch_page():
    resp = requests.get(PAGE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_offer(html):
    """Return a dict with the current offer, or None if no offer is shown."""
    def grab(field):
        m = re.search(r'name="%s"[^>]*value="([^"]*)"' % field, html)
        return m.group(1) if m else None

    discount = grab("discount_offer")
    if discount is None:
        return None
    try:
        discount = int(discount)
    except ValueError:
        return None

    return {
        "discount": discount,
        "ticket_id": grab("ticket_id"),
        "total_debit": grab("total_debit"),
        "currency": grab("currency") or "EUR",
        "original_price": grab("conplementary_price"),
    }


def build_message(offer):
    cur = offer["currency"]
    lines = [
        "🎟️ OZORA — מצאתי כרטיס עם הנחה גדולה!",
        "",
        f"💸 הנחה: {offer['discount']} {cur}",
    ]
    if offer.get("total_debit"):
        lines.append(f"💳 מחיר לתשלום: {offer['total_debit']} {cur}")
    if offer.get("original_price"):
        lines.append(f"🏷️ מחיר מקורי: {offer['original_price']} {cur}")
    if offer.get("ticket_id"):
        lines.append(f"🆔 כרטיס: {offer['ticket_id']}")
    lines += [
        "",
        "👉 פתח עכשיו, הכנס מייל ולחץ APPROVE:",
        PAGE_URL,
        "",
        "⏰ יש לך שעה לאשר במייל אחרי שתכניס אותו.",
    ]
    return "\n".join(lines)


def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=30)
    if r.ok:
        print("Telegram: sent")
        return True
    print("Telegram: FAILED", r.status_code, r.text)
    return False


def send_whatsapp(text):
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    wa_from = os.environ.get("TWILIO_FROM")
    wa_to = os.environ.get("TWILIO_TO")
    if not (sid and token and wa_from and wa_to):
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    r = requests.post(
        url,
        data={"From": wa_from, "To": wa_to, "Body": text},
        auth=(sid, token),
        timeout=30,
    )
    if r.ok:
        print("WhatsApp: sent")
        return True
    print("WhatsApp: FAILED", r.status_code, r.text)
    return False


def main():
    # Threshold is fixed at 90 EUR. (You can still override it with an
    # EUR_THRESHOLD secret if you ever want to, but you don't have to.)
    threshold = int(os.environ.get("EUR_THRESHOLD", "90"))
    print(f"Threshold: {threshold} EUR")

    try:
        html = fetch_page()
    except Exception as e:
        print("Could not fetch page:", e)
        sys.exit(0)  # don't fail the whole job on a temporary network hiccup

    offer = parse_offer(html)
    if not offer:
        print("No offer found on the page right now.")
        return

    print(f"Current discount: {offer['discount']} {offer['currency']} "
          f"(ticket {offer.get('ticket_id')}, pay {offer.get('total_debit')})")

    if offer["discount"] >= threshold:
        print("=> Discount meets threshold, sending alert!")
        msg = build_message(offer)
        sent_any = False
        sent_any |= send_telegram(msg)
        sent_any |= send_whatsapp(msg)
        if not sent_any:
            print("WARNING: no notification channel is configured!")
    else:
        print("=> Below threshold, no alert.")


if __name__ == "__main__":
    main()
