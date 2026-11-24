import time,json,logging,fcntl,os
import storage as db
import market_engine as m
logging.basicConfig(level=logging.INFO)
def run():
    db.init()
    lock=open(db.PATH+".worker.lock","a")
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    last_sol=0
    while True:
        try:
            with db.transaction() as c:
                mode,epoch,state,_=db.read(c)
                c.execute("UPDATE state SET heartbeat=? WHERE id=1",(time.time(),))
            if mode!="RUNNING":
                time.sleep(2)
                continue
            quotes,errors=m.scan_exchanges()
            state["quotes"],state["errors"]=quotes,errors
            if time.monotonic()-last_sol>=120:
                last_sol=time.monotonic()
                try: state["solana"]=m.scan_solana()
                except Exception as e: state["errors"].append(str(e)[:180])
            try: proposal,reason=m.plan(state,quotes)
            except Exception as e: proposal,reason=None,str(e)[:180]
            with db.transaction() as c:
                current,generation,_,_=db.read(c)
                if current!="RUNNING" or generation!=epoch:
                    continue
                if proposal:
                    p=proposal
                    db.event(c,"PAPER",p)
                    state["cash"][p["buy"]]-=p["paid"]
                    state["cash"][p["sell"]]+=p["received"]
                    state["inventory"][p["bk"]]+=p["qty"]
                    state["inventory"][p["sk"]]-=p["qty"]
                    state["pnl"]+=p["pnl"]
                else: db.event(c,"REJECT",{"reason":reason})
                marks={q["venue"]+"|"+q["symbol"]:q["bid"] for q in quotes}
                if state["inventory"] and all(k in marks for k in state["inventory"]):
                    state["equity"]=sum(state["cash"].values())+sum(q*marks[k] for k,q in state["inventory"].items())
                state["last_scan"]=time.time()
                c.execute("UPDATE state SET payload=?,heartbeat=? WHERE id=1",(json.dumps(state,allow_nan=False),time.time()))
        except Exception:
            logging.exception("Cycle failed; no real orders")
        time.sleep(30)
if __name__=="__main__": run()
