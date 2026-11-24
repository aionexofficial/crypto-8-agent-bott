import sqlite3, json, os, time
from contextlib import contextmanager
PATH=os.environ.get("PAPER_DB","/data/paper.sqlite3")
@contextmanager
def transaction():
    con=sqlite3.connect(PATH,timeout=20)
    try:
        con.execute("BEGIN IMMEDIATE")
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()
def init():
    os.makedirs(os.path.dirname(os.path.abspath(PATH)),exist_ok=True)
    with transaction() as c:
        c.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, mode TEXT NOT NULL, epoch INTEGER NOT NULL, payload TEXT NOT NULL, heartbeat REAL NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts REAL, kind TEXT, payload TEXT)")
        c.execute("INSERT OR IGNORE INTO state VALUES (1,'STOPPED',0,?,0)",(json.dumps(dict(cash={v:500/3 for v in ['Binance','Bitget','HTX']},inventory={},pnl=0,quotes=[],solana=[],errors=[],equity=1000)),))
def read(c):
    mode,epoch,payload,hb=c.execute("SELECT mode,epoch,payload,heartbeat FROM state WHERE id=1").fetchone()
    return mode,epoch,json.loads(payload),hb
def event(c,kind,payload):
    c.execute("INSERT INTO events(ts,kind,payload) VALUES (?,?,?)",(time.time(),kind,json.dumps(payload,allow_nan=False)))
def control(action):
    with transaction() as c:
        mode,epoch,_,_=read(c)
        if mode=="EMERGENCY" and action!="RESET":
            raise ValueError("Önce acil kilidi sıfırlayın")
        if action=="RESET" and mode!="EMERGENCY":
            raise ValueError("Acil kilit aktif değil")
        target={"START":"RUNNING","STOP":"STOPPED","EMERGENCY":"EMERGENCY","RESET":"STOPPED"}[action]
        c.execute("UPDATE state SET mode=?,epoch=? WHERE id=1",(target,epoch+1))
        event(c,"CONTROL",{"mode":target})
        return target
