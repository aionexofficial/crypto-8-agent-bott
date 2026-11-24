import requests
def notify(token,chat_id,message):
    if not token or not chat_id: return False
    try:
        r=requests.post("https://api.telegram.org/bot"+token+"/sendMessage",json={"chat_id":chat_id,"text":message},timeout=5)
        return r.ok and r.json().get("ok",False)
    except Exception: return False
