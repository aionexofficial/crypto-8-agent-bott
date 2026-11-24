import json,datetime
def report(events):
    days={}
    for ts,kind,payload in events:
        day=datetime.datetime.fromtimestamp(ts,datetime.timezone.utc).date().isoformat()
        d=days.setdefault(day,{"UTC gün":day,"Sanal işlem":0,"Red":0,"Net fark USDT":0.0})
        if kind=="PAPER":
            d["Sanal işlem"]+=1
            d["Net fark USDT"]+=float(json.loads(payload)["pnl"])
        elif kind=="REJECT": d["Red"]+=1
    return sorted(days.values(),key=lambda x:x["UTC gün"])
