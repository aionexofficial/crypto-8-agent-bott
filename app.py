import os
import time
import json
import streamlit as st
os.environ.setdefault("PAPER_DB","/tmp/crypto-paper-v3.sqlite3")
import storage as db
import market_engine as m
import solana_agents as agents
from reports import report
import hmac
from telegram_alerts import notify
st.set_page_config(page_title="Kripto Masası V8",page_icon="🤖")
st.title("🤖 8 Ajanlı Kripto Masası V8")
st.caption("Ücretsiz Streamlit modu • yalnızca sanal işlemler")
st.warning("Tarama yalnızca aktif oturumda çalışır. Yerel SQLite dosyası sunucu yeniden kurulursa silinebilir. Bu panelin kontrolleri tüm ziyaretçiler için ortaktır; özel kullanım için Streamlit erişimini sınırlandırın.")
db.init()
try: secret=st.secrets.get("PANEL_PASSWORD","")
except Exception: secret=""
password=st.text_input("Yönetici şifresi",type="password")
authorized=bool(secret) and hmac.compare_digest(password,secret)
if not authorized: st.info("Yönetim kilitli. Streamlit Secrets içinde PANEL_PASSWORD ayarlayın.")
try:
    tg_token=st.secrets.get("TELEGRAM_BOT_TOKEN","")
    tg_chat=st.secrets.get("TELEGRAM_CHAT_ID","")
except Exception: tg_token,tg_chat="",""
if authorized:
    if st.button("Telegram test bildirimi",disabled=not bool(tg_token and tg_chat)):
        if notify(tg_token,tg_chat,"V8 test: yalnızca sanal işlemler."): st.success("Telegram bildirimi gönderildi")
        else: st.error("Telegram bildirimi başarısız")
with db.transaction() as c:
    mode,_,_,_=db.read(c)
for label,action in [("Başlat","START"),("Durdur","STOP"),("ACİL DURDUR","EMERGENCY"),("Acil kilidi sıfırla (başlatmaz)","RESET")]:
    if st.button(label,key=action,disabled=not authorized):
        try:
            db.control(action)
            st.rerun()
        except ValueError as e: st.error(str(e))
@st.fragment(run_every=30)
def panel():
    with db.transaction() as c:
        mode,epoch,state,hb=db.read(c)
        due=authorized and mode=="RUNNING" and time.time()-hb>=90
        if due:
            c.execute("UPDATE state SET heartbeat=? WHERE id=1",(time.time(),))
    if due:
        try:
            quotes,errors=m.scan_exchanges()
            state["quotes"],state["errors"]=quotes,errors
            if time.time()-state.get("last_sol",0)>=120:
                state["last_sol"]=time.time()
                try: state["solana"]=agents.inspect(m.scan_solana())
                except Exception as e: state["errors"].append(str(e)[:180])
            try: p,reason=m.plan(state,quotes)
            except Exception as e: p,reason=None,str(e)[:180]
            committed=False
            with db.transaction() as c:
                current,generation,_,_=db.read(c)
                if current=="RUNNING" and generation==epoch:
                    if p:
                        db.event(c,"PAPER",p)
                        committed=True
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
            if committed and not notify(tg_token,tg_chat,f"V8 SANAL: {p['symbol']} {p['buy']} → {p['sell']} | Net fark: {p['pnl']:.6f} USDT") and tg_token and tg_chat:
                st.warning("Telegram bildirimi gönderilemedi")
        except Exception as e: st.error(str(e)[:180])
    with db.transaction() as c:
        mode,_,state,hb=db.read(c)
        events=c.execute("SELECT ts,kind,payload FROM events ORDER BY id DESC").fetchall()
    st.write("Durum:",mode)
    st.metric("Sanal portföy (son tam fiyat seti)",f'{state["equity"]:.4f} USDT')
    st.metric("Arbitraj farkı toplamı",f'{state["pnl"]:.6f} USDT')
    st.caption("İşlem limiti 10 USDT / %1 • kayma %2 • varsayımsal komisyon %0,1")
    st.subheader("Borsa fiyatları")
    st.dataframe(state["quotes"])
    st.subheader("Solana gözlem")
    st.dataframe(state["solana"])
    st.write(state["errors"])
    st.caption("Balina göstergesi hesap yoğunluğudur, transfer takibi değildir. Hype göstergesi hacim/likidite oranıdır, sosyal medya analizi değildir.")
    st.subheader("8 ajan")
    st.write("Scanner: fiyatlar | Risk: limitler | Sniper: sanal dolum | Whale: hesap yoğunluğu | Rug: kısmi RPC | Exit: iki taraflı arbitraj | Hype: hacim göstergesi | Manager: raporlar")
    st.subheader("İşlem günlüğü")
    st.dataframe([dict(time=t,kind=k,detail=p) for t,k,p in events[:200]])
    st.subheader("Günlük performans (UTC)")
    daily=report(events)
    st.dataframe(daily)
    if daily: st.line_chart(daily,x="UTC gün",y="Net fark USDT")
    st.caption("30 günlük test hedefi; gözlenen gün: "+str(len(daily))+". Kesintisiz çalışma kanıtı değildir.")
    st.download_button("Günlüğü indir",json.dumps(events,ensure_ascii=False),"paper-log.json","application/json")
panel()
