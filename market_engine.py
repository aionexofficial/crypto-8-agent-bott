import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import time
import math

CAPITAL = 1000.0
MAX_TRADE = CAPITAL * 0.01
MAX_SLIPPAGE = 0.02
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]

def api(url, params=None):
    import time
    for attempt in range(2):
        try:
            response = requests.get(url, params=params, timeout=6)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if attempt == 1:
                raise
            time.sleep(0.5)

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


import time
import math

FEE = 0.001
VENUES = ["Binance", "Bitget", "HTX"]


def depth(venue,symbol):
    if venue=="Binance":
        return api("https://data-api.binance.vision/api/v3/depth",{"symbol":symbol,"limit":20})
    if venue=="Bitget":
        return api("https://api.bitget.com/api/v2/spot/market/orderbook",{"symbol":symbol,"type":"step0","limit":"20"})["data"]
    return api("https://api.huobi.pro/market/depth",{"symbol":symbol.lower(),"type":"step0","depth":20})["tick"]

def fill(levels,qty,buy):
    levels=sorted([(float(p),float(q)) for p,q,*_ in levels if float(p)>0 and float(q)>0],reverse=not buy)
    left,total=qty,0.
    for p,q in levels:
        used=min(left,q)
        total+=used*p
        left-=used
        if left<=1e-10:
            return total,abs(total/qty/levels[0][0]-1)
    raise ValueError("Yetersiz derinlik")

def plan(state,quotes):
    marks={q["venue"]+"|"+q["symbol"]:q["bid"] for q in quotes}
    if len(marks)!=len(VENUES)*len(SYMBOLS):
        return None,"Eksik fiyat; işlem yok"
    if not state["inventory"]:
        state["inventory"]={k:(500/len(marks))/p for k,p in marks.items()}
    equity=sum(state["cash"].values())+sum(q*marks[k] for k,q in state["inventory"].items())
    for op in compare(quotes)[:1]:
        if op["Illustrative net %"]<=0:
            return None,"Komisyon sonrası fark yok"
        buy,sell,symbol=op["Buy"],op["Sell"],op["Pair"]
        bk,sk=buy+"|"+symbol,sell+"|"+symbol
        started=time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(depth,buy,symbol)
            b=pool.submit(depth,sell,symbol)
            asks,bids=a.result()["asks"],b.result()["bids"]
        if time.monotonic()-started>3:
            return None,"Defter gecikmesi"
        best=min(float(x[0]) for x in asks if float(x[1])>0)
        budget=min(10.,equity*.01,state["cash"][buy])
        qty=min(budget/(best*(1+FEE)*(1+MAX_SLIPPAGE)),state["inventory"][sk])
        if qty<=0:
            return None,"Sanal envanter yetersiz"
        cost,sl1=fill(asks,qty,True)
        proceeds,sl2=fill(bids,qty,False)
        paid,received=cost*(1+FEE),proceeds*(1-FEE)
        pnl=received-paid
        if not all(map(math.isfinite,[paid,received,pnl,qty,sl1,sl2])) or max(sl1,sl2)>MAX_SLIPPAGE or paid>budget or pnl<=0:
            return None,"Risk kontrolü reddetti"
        return dict(buy=buy,sell=sell,symbol=symbol,bk=bk,sk=sk,qty=qty,paid=paid,received=received,pnl=pnl,slippage=max(sl1,sl2)),"Varsayımsal dolum"
    return None,"Fiyat farkı yok"
