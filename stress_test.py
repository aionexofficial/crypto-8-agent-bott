import random
from market_engine import fill,FEE,MAX_SLIPPAGE
def stress(seed=42):
    rng=random.Random(seed)
    balance=1000.
    rows=[]
    for i in range(50):
        budget=balance*.10
        change=rng.uniform(-.35,.45)
        qty=budget/(100*(1+FEE)*(1+MAX_SLIPPAGE))
        try:
            cost,s1=fill([[100,qty*.2],[100*(1+rng.uniform(0,.12)),qty]],qty,True)
            proceeds,s2=fill([[100*(1+change),qty if i%7 else qty*.1]],qty,False)
            paid=cost*(1+FEE)
            if max(s1,s2)>MAX_SLIPPAGE or paid>budget: raise ValueError("Risk limiti")
            pnl=proceeds*(1-FEE)-paid
            balance+=pnl
            status="Sanal dolum"
        except ValueError as e:
            pnl=0.
            status=str(e)
        rows.append({"Test":i+1,"Bütçe":round(budget,2),"Fiyat hareketi %":round(change*100,2),"K/Z":round(pnl,4),"Bakiye":round(balance,4),"Durum":status})
    return rows
