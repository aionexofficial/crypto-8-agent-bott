import requests
def rpc(method,params):
    r=requests.post("https://api.mainnet-beta.solana.com",json={"jsonrpc":"2.0","id":1,"method":method,"params":params},timeout=5)
    r.raise_for_status()
    return r.json()["result"]
def inspect(rows):
    out=[]
    for row in rows[:3]:
        x=dict(row)
        x.update({"Mint":"Bilinmiyor","Freeze":"Bilinmiyor","İlk 20 hesap payı %":None})
        try:
            address=x["Address"]
            info=rpc("getAccountInfo",[address,{"encoding":"jsonParsed"}])["value"]["data"]["parsed"]["info"]
            x["Mint"]="Kapalı" if info["mintAuthority"] is None else "Aktif"
            x["Freeze"]="Kapalı" if info["freezeAuthority"] is None else "Aktif"
            supply=int(info["supply"])
            accounts=rpc("getTokenLargestAccounts",[address])["value"]
            if supply>0: x["İlk 20 hesap payı %"]=round(100*sum(int(a["amount"]) for a in accounts)/supply,2)
        except Exception as e: x["RPC hata"]=str(e)[:120]
        try:
            liq=float(x["Liquidity USD"] or 0)
            x["Hacim / likidite"]=float(x["24h volume USD"] or 0)/liq if liq>0 else None
        except Exception: pass
        x["Karar"]="İşlem kapalı: LP ve satış güvenliği doğrulanmadı"
        out.append(x)
    return out
