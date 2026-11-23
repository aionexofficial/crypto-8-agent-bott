import streamlit as st
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

st.set_page_config(page_title="8 Agent Paper Desk", page_icon="🤖", layout="wide")
CAPITAL = 1000.0
MAX_TRADE = CAPITAL * 0.01
MAX_SLIPPAGE = 0.02
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]

def api(url, params=None):
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()

def binance(symbol):
    d = api("https://data-api.binance.vision/api/v3/ticker/bookTicker", {"symbol": symbol})
    return dict(venue="Binance", symbol=symbol, bid=float(d["bidPrice"]), ask=float(d["askPrice"]), bid_qty=float(d["bidQty"]), ask_qty=float(d["askQty"]))

def bitget(symbol):
    d = api("https://api.bitget.com/api/v2/spot/market/tickers", {"symbol": symbol})
    if d.get("code") != "00000" or not d.get("data"):
        raise ValueError("Bitget returned no data")
    x = d["data"][0]
    return dict(venue="Bitget", symbol=symbol, bid=float(x["bidPr"]), ask=float(x["askPr"]), bid_qty=float(x["bidSz"]), ask_qty=float(x["askSz"]))

def htx(symbol):
    d = api("https://api.huobi.pro/market/detail/merged", {"symbol": symbol.lower()})
    if d.get("status") != "ok":
        raise ValueError("HTX returned no data")
    x = d["tick"]
    return dict(venue="HTX", symbol=symbol, bid=float(x["bid"][0]), ask=float(x["ask"][0]), bid_qty=float(x["bid"][1]), ask_qty=float(x["ask"][1]))

def scan_exchanges():
    jobs = [(fn, symbol) for symbol in SYMBOLS for fn in (binance, bitget, htx)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fn, symbol) for fn, symbol in jobs]
        quotes, errors = [], []
        for (fn, symbol), future in zip(jobs, futures):
            try:
                q = future.result()
                if q["bid"] > 0 and q["ask"] > 0:
                    quotes.append(q)
            except Exception as exc:
                errors.append(f"{fn.__name__} {symbol}: {str(exc)[:100]}")
    return quotes, errors

def compare(quotes):
    opportunities = []
    for symbol in SYMBOLS:
        subset = [q for q in quotes if q["symbol"] == symbol]
        for buy in subset:
            for sell in subset:
                if buy["venue"] == sell["venue"]:
                    continue
                gross = (sell["bid"] / buy["ask"] - 1) * 100
                if gross <= 0:
                    continue
                quantity = MAX_TRADE / buy["ask"]
                capacity = buy["ask_qty"] >= quantity and sell["bid_qty"] >= quantity
                estimated_net = gross - 0.2  # illustrative 0.1% fee per side; not verified
                opportunities.append({
                    "Pair": symbol, "Buy": buy["venue"], "Sell": sell["venue"],
                    "Gross %": round(gross, 4), "Illustrative net %": round(estimated_net, 4),
                    "Paper size USDT": MAX_TRADE,
                    "Top-of-book capacity": "yes" if capacity else "no",
                    "Decision": "REJECTED: slippage / transfers / fees unverified",
                })
    return sorted(opportunities, key=lambda r: r["Illustrative net %"], reverse=True)

def scan_solana():
    profiles = api("https://api.dexscreener.com/token-profiles/latest/v1")
    addresses = []
    for p in profiles if isinstance(profiles, list) else []:
        address = p.get("tokenAddress")
        if p.get("chainId") == "solana" and address and address not in addresses:
            addresses.append(address)
        if len(addresses) >= 10:
            break
    if not addresses:
        return []
    pairs = api("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(addresses))
    rows = []
    for p in pairs if isinstance(pairs, list) else []:
        if p.get("chainId") != "solana":
            continue
        rows.append({
            "Token": (p.get("baseToken") or {}).get("symbol", "?"),
            "Address": (p.get("baseToken") or {}).get("address", ""),
            "DEX": p.get("dexId", ""),
            "Price USD": p.get("priceUsd"),
            "Liquidity USD": (p.get("liquidity") or {}).get("usd", 0),
            "24h volume USD": (p.get("volume") or {}).get("h24", 0),
            "Decision": "REJECTED: mint/freeze/LP/honeypot/slippage not verified",
        })
    return sorted(rows, key=lambda x: x["Liquidity USD"] or 0, reverse=True)[:25]

st.title("🤖 8 Agent Crypto Paper Desk")
st.caption("READ-ONLY public market data • no exchange keys • no wallet • no orders • no withdrawals")
a, b, c = st.columns(3)
a.metric("Virtual capital", "1,000 USDT")
b.metric("Maximum paper trade", "10 USDT (1%)")
c.metric("Slippage ceiling", "2% — NOT VERIFIED")
st.warning("Safety lock: ALL trade proposals are rejected. Top-of-book quotes cannot prove slippage, execution, available balances or arbitrage profitability.")
if st.button("🔄 Scan Binance / Bitget / HTX", type="primary"):
    with st.spinner("Reading public order quotes..."):
        st.session_state["quotes"], st.session_state["errors"] = scan_exchanges()
        st.session_state["quote_time"] = datetime.now(timezone.utc).isoformat()
if "quotes" in st.session_state:
    st.caption("Last quote request (UTC): " + st.session_state["quote_time"])
    if st.session_state["errors"]:
        st.info("Data source errors: " + "; ".join(st.session_state["errors"]))
    st.subheader("Observed bid / ask")
    st.dataframe(st.session_state["quotes"], use_container_width=True)
    st.subheader("Cross-exchange price differences (not executable trades)")
    st.dataframe(compare(st.session_state["quotes"]), use_container_width=True)
st.divider()
st.subheader("Solana token observation")
if st.button("🪙 Scan recent Solana token profiles"):
    try:
        st.session_state["solana"] = scan_solana()
    except Exception as exc:
        st.error("Solana API unavailable: " + str(exc)[:180])
if "solana" in st.session_state:
    st.dataframe(st.session_state["solana"], use_container_width=True)
    st.error("DEX Screener profiles are not all new mints. Token safety checks are not implemented.")
st.divider()
st.subheader("Eight agent roles")
st.dataframe([
    {"Agent": "Scanner", "Status": "Active: public exchange and Solana observations"},
    {"Agent": "Risk", "Status": "Partial: 10 USDT cap; all proposals blocked"},
    {"Agent": "Sniper", "Status": "Calculation only; no execution"},
    {"Agent": "Whale", "Status": "Not integrated"},
    {"Agent": "Rug", "Status": "Not integrated; no tokens approved"},
    {"Agent": "Exit", "Status": "Inactive: no positions"},
    {"Agent": "Hype", "Status": "Not integrated"},
    {"Agent": "Desk Manager", "Status": "Dashboard only"},
], use_container_width=True)
st.caption("Manual scans only. No 24/7 background operation and no completed paper trades in V1.")
