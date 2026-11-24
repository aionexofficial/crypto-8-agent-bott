import os
import time
import json
import streamlit as st
os.environ.setdefault("PAPER_DB","/tmp/crypto-paper-v3.sqlite3")
import storage as db
import market_engine as m
st.set_page_config(page_title="Kripto Masası V3",page_icon="🤖")
st.title("🤖 8 Ajanlı Kripto Masası V3")
st.caption("Ücretsiz Streamlit modu • yalnızca sanal işlemler")
st.warning("Tarama yalnızca aktif oturumda çalışır. Yerel SQLite dosyası sunucu yeniden kurulursa silinebilir. Bu panelin kontrolleri tüm ziyaretçiler için ortaktır; özel kullanım için Streamlit erişimini sınırlandırın.")
db.init()
with db.transaction() as c:
    mode,_,_,_=db.read(c)
for label,action in [("Başlat","START"),("Durdur","STOP"),("ACİL DURDUR","EMERGENCY"),("Acil kilidi sıfırla (başlatmaz)","RESET")]:
    if st.button(label,key=action):
        try:
            db.control(action)
            st.rerun()
        except ValueError as e: st.error(str(e))
@st.fragment(run_every=30)
def panel():
    with db.transaction() as c:
        mode,epoch,state,hb=db.read(c)
        due=mode=="RUNNING" and time.time()-hb>=30
        if due:
            c.execute("UPDATE state SET heartbeat=? WHERE id=1",(time.time(),))
    if due:
        try:
            quotes,errors=m.scan_exchanges()
            state["quotes"],state["errors"]=quotes,errors
            if time.time()-state.get("last_sol",0)>=120:
                state["last_sol"]=time.time()
                try: state["solana"]=m.scan_solana()
                except Exception as e: state["errors"].append(str(e)[:180])
            try: p,reason=m.plan(state,quotes)
            except Exception as e: p,reason=None,str(e)[:180]
            with db.transaction() as c:
                current,generation,_,_=db.read(c)
                if current=="RUNNING" and generation==epoch:
                    if p:
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
        except Exception as e: st.error(str(e)[:180])
    with db.transaction() as c:
        mode,_,state,hb=db.read(c)
        events=c.execute("SELECT ts,kind,payload FROM events ORDER BY id DESC LIMIT 200").fetchall()
    st.write("Durum:",mode)
    st.metric("Sanal portföy (son tam fiyat seti)",f'{state["equity"]:.4f} USDT')
    st.metric("Arbitraj farkı toplamı",f'{state["pnl"]:.6f} USDT')
    st.caption("İşlem limiti 10 USDT / %1 • kayma %2 • varsayımsal komisyon %0,1")
    st.subheader("Borsa fiyatları")
    st.dataframe(state["quotes"])
    st.subheader("Solana gözlem")
    st.dataframe(state["solana"])
    st.write(state["errors"])
    st.subheader("İşlem günlüğü")
    st.dataframe([dict(time=t,kind=k,detail=p) for t,k,p in events])
    st.download_button("Günlüğü indir",json.dumps(events,ensure_ascii=False),"paper-log.json","application/json")
panel()
