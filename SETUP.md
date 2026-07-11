# Daily Fidelity Portfolio Push — Setup

Stack: SnapTrade (read-only Fidelity data, Personal API key) → GitHub Actions (free scheduler) → ntfy.sh (free push) → your phone.

## 1. SnapTrade account (done)

You already have a SnapTrade Personal account set up with Fidelity connected, using **SDK** access (client ID starting with `PERS-`). That means:

- No user registration step — the API key itself identifies you as the account owner.
- No `userId`/`userSecret` to create, store, or rotate — just the two key values from the dashboard (Settings → API Keys):
  - `SNAPTRADE_CLIENT_ID`
  - `SNAPTRADE_CONSUMER_KEY`

## 2. Link your Fidelity account (one-time, on your own computer)

```bash
cd portfolio_alerts
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export SNAPTRADE_CLIENT_ID=your_client_id
export SNAPTRADE_CONSUMER_KEY=your_consumer_key
python setup_snaptrade.py
```

Note: `requirements.txt` pins `snaptrade-python-sdk==12.0.0rc0` — a release candidate. This is intentional, not a mistake: SnapTrade's current *stable* SDK only documents the older Commercial (multi-user) flow, and Personal API key auth (no userId/userSecret) requires the rc per SnapTrade's own docs. If a later stable release adds proper Personal support, this can be re-pinned.

Running the script prints a URL — open it in your browser, log into Fidelity through SnapTrade's connection portal (this is Fidelity's own consent screen; SnapTrade never sees your password), and approve read-only access. Back in the terminal, press Enter to continue. It then prints your connections and accounts so you can confirm Fidelity is actually linked.

Every new terminal session needs `source venv/bin/activate` again before running these scripts.

## 3. Verify the numbers against your real account

The field lookups in `daily_check.py` (total account value, per-position market value) were checked directly against the SnapTrade SDK's source/type definitions, not guessed — but do one dry run before trusting it:

```bash
DEBUG=1 python daily_check.py
```

This prints the raw JSON for accounts/positions along with the computed message, without pushing or saving anything. Check that the total dollar value looks right. If something's off, paste the raw output back and I'll adjust it.

Once it looks right, run it for real once (no `DEBUG`) to create the first `state.json` baseline:

```bash
python daily_check.py
```

## 4. Put it on GitHub

1. Create a **private** GitHub repo, push the `portfolio_alerts/` folder and `.github/workflows/portfolio_check.yml` to it.
2. Repo → **Settings → Secrets and variables → Actions → New repository secret**, add:
   - `SNAPTRADE_CLIENT_ID`
   - `SNAPTRADE_CONSUMER_KEY`
   - `NTFY_TOPIC` — see step 5

Only three secrets now — Personal auth doesn't need a stored user secret.

## 5. Set up push notifications

1. Pick a random, hard-to-guess topic name (e.g. `gram-portfolio-9f3k2x`) — **ntfy.sh topics are public by default**, anyone who knows the exact name can read or post to it, so don't use something guessable like `gram-portfolio`.
2. Install the **ntfy** app (iOS App Store / Google Play Store).
3. In the app, subscribe to your topic name.
4. Set that same string as the `NTFY_TOPIC` GitHub secret.

## 6. Test end to end

Repo → **Actions** tab → "Daily Portfolio Check" → **Run workflow** (uses the `workflow_dispatch` trigger, no need to wait for the schedule). You should get a push on your phone within a minute or two.

## 7. Let it run

The schedule fires weekday mornings (~9:35am ET during Daylight Time, ~8:35am during Standard Time — GitHub cron is fixed UTC and doesn't shift with US clock changes; see the comment in the workflow file if you want to fix that). Each run commits an updated `state.json` back to the repo so the next run has yesterday's numbers to diff against.

## Next step: per-holding "big jump" alerts

This build covers the daily summary. The same SnapTrade + ntfy pieces can be extended with a second, more frequent workflow (e.g. every 30 min during market hours) that checks each position against a % threshold and only pushes when something crosses it — happy to build that next once the daily digest is confirmed working with real numbers.
