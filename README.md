# 8 Agent Crypto Paper Desk — V1

Read-only Streamlit research dashboard for iPhone. This is **not** a working autonomous trading bot.

## Safety settings
- Virtual capital: 1,000 USDT
- Maximum hypothetical position: 10 USDT (1%)
- Maximum slippage policy: 2%, **not measurable in V1**, therefore every proposal is rejected
- No order endpoints, no wallet, no exchange credentials, no transfers or withdrawals
- No actual paper-trade fills or P&L ledger yet

## Features
- On-demand public bid/ask snapshots: Binance, Bitget, HTX
- Cross-venue spread estimates with illustrative (not verified) 0.1% per-side fee
- Recent Solana token profiles and DEX liquidity from DEX Screener
- Eight named roles, with inactive integrations clearly identified
- API failures shown without pretending missing prices are zero

## Deploy from iPhone
1. Open https://share.streamlit.io and sign in with GitHub.
2. Select **Create app** > repository **aionexofficial/crypto-8-agent-bott**, branch **main**, entry point **app.py**.
3. Deploy. In Safari open the Streamlit URL; Share > Add to Home Screen.
4. Press either scan button. Streamlit Community Cloud may sleep; scans do not run in the background.

Never upload a seed phrase, private key or API secret. No guaranteed profits or rug-pull protection. Exchange fees, depth, timing, slippage, transfers and capital placement are not modeled.
