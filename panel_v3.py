import streamlit as st
import os,time,hmac,json
import storage as db
st.set_page_config(page_title="Kripto Masası V3",page_icon="🤖")
st.title("Kripto Masası V3")
st.caption("Yalnızca sanal işlemler • 1.000 USDT • %1 • %2")
secret=os.environ.get("PANEL_PASSWORD","")
if not secret:
    st.error("Sunucuda PANEL_PASSWORD ayarlanmalı.")
    st.stop()
password=st.text_input("Panel şifresi",type="password")
if not hmac.compare_digest(password,secret): st.stop()
db.init()
@st.fragment(run_every=5)
def panel():
    with db.transaction() as c:
        mode,epoch,state,hb=db.read(c)
        events=c.execute("SELECT ts,kind,payload FROM events ORDER BY id DESC LIMIT 100").fetchall()
    st.write("Durum:",mode)
    st.write("Worker:", "Son 120 sn içinde aktif" if time.time()-hb<120 else "Çevrimdışı / gecikmiş")
    for label,action in [("Başlat","START"),("Durdur","STOP"),("ACİL DURDUR","EMERGENCY"),("Acil kilidi sıfırla (başlatmaz)","RESET")]:
        if st.button(label,key=action):
            try: db.control(action); st.rerun(scope="fragment")
            except ValueError as e: st.error(str(e))
    st.metric("Son hesaplanan sanal portföy",f'{state["equity"]:.4f} USDT')
    st.metric("Arbitraj farkı toplamı",f'{state["pnl"]:.6f} USDT')
    st.caption("Portföy değeri son eksiksiz fiyat setine aittir; komisyon varsayımsaldır.")
    st.dataframe(state["quotes"])
    st.dataframe(state["solana"])
    st.write(state["errors"])
    st.dataframe([dict(time=t,kind=k,detail=p) for t,k,p in events])
panel()
