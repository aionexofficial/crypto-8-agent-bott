import streamlit as st
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import time
import math

st.set_page_config(page_title="8 Agent Paper Desk", page_icon="🤖", layout="wide")
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
import pandas as pd

FEE = 0.001
VENUES = ["Binance", "Bitget", "HTX"]

def depth(venue, symbol):
    if venue == "Binance":
        d = api("https://data-api.binance.vision/api/v3/depth", {"symbol":symbol,"limit":20})
    elif venue == "Bitget":
        d = api("https://api.bitget.com/api/v2/spot/market/orderbook", {"symbol":symbol,"type":"step0","limit":"20"})["data"]
    else:
        d = api("https://api.huobi.pro/market/depth", {"symbol":symbol.lower(),"type":"step0","depth":20})["tick"]
    return d

def fill(levels, quantity, buy):
    levels = sorted([(float(p),float(q)) for p,q,*_ in levels if float(p)>0 and float(q)>0], reverse=not buy)
    remaining, total = quantity, 0.0
    for p,q in levels:
        used = min(remaining,q)
        total += used*p
        remaining -= used
        if remaining <= 1e-10:
            return total, abs(total/quantity/levels[0][0]-1)
    raise ValueError("Yetersiz emir defteri")

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def initial():
    return {"cash":{v:500/3 for v in VENUES},"inventory":{}, "marks":{}, "history":[], "pnl":0.0,"curve":[0.0],"quotes":[],"errors":[],"solana":[],"last_sol":0.0,"last_scan":"","initialized":False}

if "v2" not in st.session_state:
    st.session_state.v2 = initial()
s = st.session_state.v2

def record(symbol,buy,sell,status,reason,pnl=0.0):
    s["history"].append({"UTC":now(),"Parite":symbol,"Alış":buy,"Satış":sell,"Durum":status,"Gerekçe":reason,"Net USDT":round(pnl,8)})
    s["history"] = s["history"][-2000:]

def cycle():
    quotes, errors = scan_exchanges()
    s["quotes"],s["errors"],s["last_scan"] = quotes,errors,now()
    for q in quotes:
        s["marks"][(q["venue"],q["symbol"])] = q["bid"]
    if not s["initialized"]:
        if len(quotes) != len(VENUES)*len(SYMBOLS):
            return
        for q in quotes:
            s["inventory"][(q["venue"],q["symbol"])] = (500/15)/q["bid"]
        s["initialized"] = True
    for op in compare(quotes)[:5]:
        symbol,buy,sell = op["Pair"],op["Buy"],op["Sell"]
        if op["Illustrative net %"] <= 0:
            record(symbol,buy,sell,"RED","Tahmini komisyon sonrası kâr yok")
            continue
        try:
            start = time.monotonic()
            with ThreadPoolExecutor(max_workers=2) as pool:
                f1=pool.submit(depth,buy,symbol)
                f2=pool.submit(depth,sell,symbol)
                a,b=f1.result(),f2.result()
            if time.monotonic()-start > 3:
                raise ValueError("Emir defteri gecikmesi > 3 saniye")
            best=min(float(x[0]) for x in a["asks"] if float(x[1])>0)
            equity=sum(s["cash"].values())+sum(q*s["marks"].get(k,0) for k,q in s["inventory"].items())
            budget=min(10.0,equity*0.01,s["cash"][buy])
            qty=min(budget/(best*(1+FEE)*(1+MAX_SLIPPAGE)),s["inventory"].get((sell,symbol),0))
            if qty <= 0:
                raise ValueError("Sanal borsa bakiyesi yetersiz")
            cost,sl1=fill(a["asks"],qty,True)
            proceeds,sl2=fill(b["bids"],qty,False)
            paid=cost*(1+FEE)
            received=proceeds*(1-FEE)
            pnl=received-paid
            if max(sl1,sl2)>MAX_SLIPPAGE or paid>budget or pnl<=0:
                raise ValueError("Kayma, sermaye limiti veya net kâr kontrolü başarısız")
            record(symbol,buy,sell,"SANAL",f"Model kayma: %{100*max(sl1,sl2):.4f}; varsayımsal komisyon",pnl)
            s["cash"][buy]-=paid
            s["cash"][sell]+=received
            s["inventory"][(buy,symbol)]=s["inventory"].get((buy,symbol),0)+qty
            s["inventory"][(sell,symbol)]-=qty
            s["pnl"]+=pnl
            s["curve"].append(s["pnl"])
        except Exception as exc:
            record(symbol,buy,sell,"RED",str(exc)[:180])
    if time.monotonic()-s["last_sol"]>=60:
        s["last_sol"]=time.monotonic()
        try:
            s["solana"]=scan_solana()
            for row in s["solana"]:
                row["Decision"]="RED: mint/LP/honeypot/kayma doğrulanmadı"
        except Exception as exc:
            s["errors"].append("Solana: "+str(exc)[:150])


# Public order books only. No authenticated endpoints or order methods.
def depth(venue, symbol):
    if venue == "Binance":
        d = api("https://data-api.binance.vision/api/v3/depth", {"symbol":symbol,"limit":20})
    elif venue == "Bitget":
        d = api("https://api.bitget.com/api/v2/spot/market/orderbook", {"symbol":symbol,"limit":"20"})["data"]
    else:
        d = api("https://api.huobi.pro/market/depth", {"symbol":symbol.lower(),"type":"step0","depth":20})["tick"]
    return {side: [(float(p),float(q)) for p,q,*_ in d[side] if float(p)>0 and float(q)>0] for side in ("asks","bids")}

def fill(levels, qty):
    left, value = qty, 0.0
    for p,q in levels:
        take = min(left,q)
        value += take*p
        left -= take
        if left <= 1e-10:
            return value
    raise ValueError("Yetersiz emir defteri derinliği")

def simulate(candidate, capital, fee):
    symbol, buy, sell = candidate["Pair"], candidate["Buy"], candidate["Sell"]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(depth,buy,symbol)
        b = pool.submit(depth,sell,symbol)
        asks = sorted(a.result()["asks"])
        bids = sorted(b.result()["bids"],reverse=True)
    if time.monotonic()-started > 3 or not asks or not bids:
        raise ValueError("Veri gecikmesi veya boş defter")
    # Reserve fee and worst allowed slippage within the 1% budget.
    budget = min(capital*0.01,10.0)
    qty = budget/(asks[0][0]*(1+MAX_SLIPPAGE)*(1+fee))
    cost, proceeds = fill(asks,qty),fill(bids,qty)
    slip_buy = cost/qty/asks[0][0]-1
    slip_sell = 1-proceeds/qty/bids[0][0]
    if max(slip_buy,slip_sell)>MAX_SLIPPAGE or cost*(1+fee)>budget:
        raise ValueError("Kayma veya sermaye limiti")
    pnl = proceeds*(1-fee)-cost*(1+fee)
    if not math.isfinite(pnl) or pnl<=0:
        raise ValueError("Komisyon sonrası pozitif fark yok")
    return pnl, cost*(1+fee), max(slip_buy,slip_sell)*100

st.title("🤖 8 Ajanlı Kripto Masası V2")
st.caption("Sadece simülasyon • Gerçek emir, cüzdan ve para çekme yok")
s=st.session_state
if "ledger" not in s:
    s.ledger=[]
    s.balance=CAPITAL
    s.curve=[CAPITAL]
    s.last_sol=0.0
    s.quotes=[]
    s.errors=[]
    s.opps=[]
auto=st.toggle("Otomatik tarama (sayfa açıkken, 30 saniye)",value=False)
paper=st.toggle("Varsayımsal arbitraj simülasyonu",value=False)
fee=st.number_input("Varsayılan tek yön komisyon (%)",min_value=0.0,max_value=2.0,value=0.1,step=0.01)/100
st.warning("Simülasyon iki borsada önceden hazır envanter ve eşzamanlı dolum varsayar. Gerçek bakiye, minimum emir, transfer, yeniden dengeleme ve ağ gecikmesi modellenmez. Solana işlemleri güvenlik kontrolleri eksik olduğu için kapalı.")

@st.fragment(run_every=30 if auto else None)
def panel():
    if st.button("Borsaları tara",type="primary") or auto:
        s.quotes,s.errors=scan_exchanges()
        s.opps=compare(s.quotes)
        s.quote_time=datetime.now(timezone.utc).isoformat()
        if paper:
            for candidate in s.opps[:1]:
                entry={"Zaman":s.quote_time,"Parite":candidate["Pair"],"Alış":candidate["Buy"],"Satış":candidate["Sell"],"K/Z":0.0}
                try:
                    pnl,cost,slip=simulate(candidate,s.balance,fee)
                    entry.update({"Durum":"Varsayımsal dolum","K/Z":pnl,"Tutar":cost,"Kayma %":slip})
                    s.ledger.append(entry)
                    s.balance+=pnl
                    s.curve.append(s.balance)
                except Exception as exc:
                    entry["Durum"]="Reddedildi: "+str(exc)[:150]
                    s.ledger.append(entry)
        if auto and time.monotonic()-s.last_sol>=120:
            s.last_sol=time.monotonic()
            try:
                s.solana=scan_solana()
                s.sol_error=""
            except Exception as exc:
                s.sol_error=str(exc)[:180]
    a,b,c=st.columns(3)
    a.metric("Sanal bakiye",f"{s.balance:.4f} USDT")
    b.metric("Sanal K/Z",f"{s.balance-CAPITAL:+.4f}")
    c.metric("İşlem üst sınırı","10 USDT / %1")
    st.caption("Son tarama UTC: "+s.get("quote_time","Henüz yok"))
    if s.errors:
        st.info("Veri hataları: "+"; ".join(s.errors))
    st.subheader("Borsa fiyatları")
    st.dataframe(s.quotes,use_container_width=True)
    st.subheader("Brüt farklar (gösterge, kesin kâr değil)")
    st.dataframe([{k:v for k,v in x.items() if k not in ("Decision","Illustrative net %")} for x in s.opps],use_container_width=True)
    st.subheader("Solana token taraması")
    if st.button("Solana tara"):
        try:
            s.solana=scan_solana()
            s.sol_error=""
        except Exception as exc:
            s.sol_error=str(exc)[:180]
    if s.get("sol_error"):
        st.error(s.sol_error)
    if "solana" in s:
        st.dataframe(s.solana,use_container_width=True)
    st.caption("DEX Screener profilleri yeni mint garantisi değildir. Mint, LP ve honeypot doğrulanmadı.")
    st.subheader("Sanal bakiye grafiği")
    st.line_chart(s.curve)
    st.subheader("İşlem günlüğü")
    st.dataframe(s.ledger[-200:],use_container_width=True)
    st.caption("Geçmiş yalnızca bu oturumda saklanır; sayfa kapanırsa kaybolabilir.")
panel()
st.subheader("8 ajan durumu")
st.dataframe([
    {"Ajan":"Tarayıcı","Durum":"Borsa ve Solana veri taraması"},
    {"Ajan":"Risk","Durum":"Borsa defteri, %1 limit, %2 kayma"},
    {"Ajan":"Nişancı","Durum":"Yalnızca varsayımsal dolum"},
    {"Ajan":"Balina","Durum":"Henüz entegre değil"},
    {"Ajan":"Rug","Durum":"Solana işlemleri engelli"},
    {"Ajan":"Çıkış","Durum":"Arbitraj iki taraflı simülasyon; açık pozisyon yok"},
    {"Ajan":"Hype","Durum":"Henüz entegre değil"},
    {"Ajan":"Masa yöneticisi","Durum":"Panel ve oturum günlüğü"},
],use_container_width=True)
