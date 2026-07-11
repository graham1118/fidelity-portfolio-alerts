"""
Daily portfolio check: pulls current holdings from Fidelity (via SnapTrade
Personal API key auth), compares them to yesterday's saved snapshot, and
pushes a summary notification to your phone via ntfy.sh.

AUTH: Uses SnapTrade Personal API key authentication -- client_id +
consumer_key only, no userId/userSecret. This requires
snaptrade-python-sdk==12.0.0rc0 (a release candidate); the current stable
release only documents the older Commercial-style flow. See
docs.snaptrade.com/docs/authentication-methods.

DATA SHAPE: verified directly against the 12.0.0rc0 SDK source, not guessed:
  - list_user_accounts() -> list of Account, each with balance.total.amount
    (this is the account's total value -- cash + all positions).
  - get_user_account_positions(account_id=...) -> list of Position, each with
    symbol.symbol.symbol (the ticker string), units, price. There is no
    direct market_value field, so it's computed here as units * price.

If a future SDK release changes these field names, run with DEBUG=1 to print
the raw API responses and compare against what this script expects.
"""

import json
import os
import sys
from pathlib import Path

import requests
from snaptrade_client import SnapTrade
from snaptrade_client.auth import SnapTradeAuth
from snaptrade_client.configuration import Configuration

STATE_PATH = Path(__file__).parent / "state.json"
DEBUG = os.environ.get("DEBUG") == "1"


def get_client():
    config = Configuration(
        auth=SnapTradeAuth.personal_api_key(
            consumer_key=os.environ["SNAPTRADE_CONSUMER_KEY"],
            client_id=os.environ["SNAPTRADE_CLIENT_ID"],
        )
    )
    return SnapTrade(configuration=config)


def fetch_snapshot(snaptrade):
    accounts_resp = snaptrade.account_information.list_user_accounts()
    accounts = accounts_resp.body
    if DEBUG:
        print("RAW ACCOUNTS:", json.dumps(accounts, indent=2, default=str))

    total_value = 0.0
    positions_by_symbol = {}

    for acct in accounts:
        account_id = acct["id"]
        account_name = acct.get("name") or acct.get("number") or account_id

        balance = acct.get("balance") if isinstance(acct, dict) else None
        total = balance.get("total") if isinstance(balance, dict) else None
        acct_value = total.get("amount") if isinstance(total, dict) else None
        total_value += float(acct_value or 0)

        pos_resp = snaptrade.account_information.get_user_account_positions(
            account_id=account_id
        )
        if DEBUG:
            print(f"RAW POSITIONS ({account_name}):", json.dumps(pos_resp.body, indent=2, default=str))

        for pos in pos_resp.body or []:
            if not isinstance(pos, dict):
                continue
            position_symbol = pos.get("symbol") or {}
            universal_symbol = position_symbol.get("symbol") if isinstance(position_symbol, dict) else None
            symbol = (
                universal_symbol.get("symbol") or universal_symbol.get("raw_symbol")
                if isinstance(universal_symbol, dict)
                else None
            ) or "UNKNOWN"

            units = float(pos.get("units") or pos.get("fractional_units") or 0)
            price = float(pos.get("price") or 0)
            market_value = units * price

            positions_by_symbol[symbol] = positions_by_symbol.get(symbol, 0.0) + market_value

    return {"total_value": total_value, "positions": positions_by_symbol}


def load_previous_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return None


def save_state(snapshot):
    STATE_PATH.write_text(json.dumps(snapshot, indent=2))


def format_message(prev, curr):
    if prev is None:
        return (
            f"Portfolio tracking started. Baseline saved: ${curr['total_value']:,.2f}. "
            "You'll get your first change summary tomorrow."
        )

    delta = curr["total_value"] - prev["total_value"]
    pct = (delta / prev["total_value"] * 100) if prev["total_value"] else 0.0
    arrow = "▲" if delta >= 0 else "▼"
    lines = [
        f"Portfolio: ${curr['total_value']:,.2f}  {arrow} ${abs(delta):,.2f} ({pct:+.2f}%) since last close"
    ]

    movers = []
    for symbol, value in curr["positions"].items():
        prev_value = prev["positions"].get(symbol)
        if prev_value:
            change_pct = (value - prev_value) / prev_value * 100
            movers.append((symbol, change_pct, value - prev_value))
    movers.sort(key=lambda m: abs(m[1]), reverse=True)

    for symbol, change_pct, change_amt in movers[:3]:
        m_arrow = "▲" if change_amt >= 0 else "▼"
        lines.append(f"  {symbol}: {m_arrow} {change_pct:+.2f}% (${change_amt:+,.2f})")

    return "\n".join(lines)


def send_ntfy(message, topic):
    resp = requests.post(
        f"https://ntfy.sh/{topic}",
        data=message.encode("utf-8"),
        headers={
            "Title": "Portfolio update",
            "Priority": "default",
            "Tags": "chart_with_upwards_trend",
        },
        timeout=15,
    )
    resp.raise_for_status()


def main():
    ntfy_topic = os.environ.get("NTFY_TOPIC")

    snaptrade = get_client()
    prev_state = load_previous_state()
    curr_state = fetch_snapshot(snaptrade)

    message = format_message(prev_state, curr_state)
    print(message)

    if DEBUG:
        print("\n[DEBUG mode: not sending push notification or saving state]")
        return 0

    if not ntfy_topic:
        print("NTFY_TOPIC not set -- skipping push, state not saved.", file=sys.stderr)
        return 1

    send_ntfy(message, ntfy_topic)
    save_state(curr_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
