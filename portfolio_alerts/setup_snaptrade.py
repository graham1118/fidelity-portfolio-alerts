"""
One-time LOCAL setup for SnapTrade Personal API key authentication.

Your client ID starts with PERS-, which means SnapTrade registered this as a
Personal account key. Personal keys do NOT use the Commercial
register-a-user flow -- the API key itself identifies you as the account
owner, so there's no userId/userSecret to create or store.

This requires snaptrade-python-sdk 12.0.0rc0 (a release candidate). The
current stable release only documents the older Commercial-style flow;
SnapTrade's own docs (docs.snaptrade.com/docs/authentication-methods) say to
use the rc SDK for proper Personal auth support until that lands in stable.

Run this on your own computer, NOT in GitHub Actions -- it needs an
interactive browser step.

Usage:
    pip install -r requirements.txt
    export SNAPTRADE_CLIENT_ID=your_client_id
    export SNAPTRADE_CONSUMER_KEY=your_consumer_key
    python setup_snaptrade.py
"""

import os
from pprint import pprint

from snaptrade_client import SnapTrade
from snaptrade_client.auth import SnapTradeAuth
from snaptrade_client.configuration import Configuration


def get_client():
    config = Configuration(
        auth=SnapTradeAuth.personal_api_key(
            consumer_key=os.environ["SNAPTRADE_CONSUMER_KEY"],
            client_id=os.environ["SNAPTRADE_CLIENT_ID"],
        )
    )
    return SnapTrade(configuration=config)


def main():
    snaptrade = get_client()

    status = snaptrade.api_status.check()
    print("API status:", status.body)

    # No userId/userSecret needed -- Personal API key auth resolves you
    # automatically.
    redirect = snaptrade.authentication.login_snap_trade_user()
    redirect_uri = redirect.body.get("redirectURI") if isinstance(redirect.body, dict) else redirect.body
    print(f"\nOpen this URL in your browser and connect your Fidelity account:\n{redirect_uri}")

    input("\nPress Enter once you've finished connecting Fidelity in the browser...")

    connections = snaptrade.connections.list_brokerage_authorizations()
    print("\nConnections found:")
    pprint(connections.body)

    accounts = snaptrade.account_information.list_user_accounts()
    print("\nAccounts found (these should show up in the daily check automatically):")
    pprint(accounts.body)

    if not connections.body:
        print(
            "\nNo connections found. If you just approved the Fidelity link in your "
            "browser, wait a few seconds and re-run this script -- it can take a "
            "moment to register."
        )


if __name__ == "__main__":
    main()
