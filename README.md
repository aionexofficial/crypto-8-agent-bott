# 8 Ajanlı Kripto Masası — V2 (Test)

iPhone tarayıcısından kullanılabilen, sadece **sanal işlem** yapan Streamlit kontrol paneli.

## Mevcut özellikler
- Binance, Bitget ve HTX herkese açık bid/ask verileri
- 5 USDT paritesini elle veya sayfa açıkken yaklaşık 30 saniyede tarama
- DEX Screener üzerinden Solana token profili ve likidite verileri (otomatik modda yaklaşık 120 saniyede)
- Alış/satış emir defterinde ilk 20 seviyeye göre varsayımsal işlem, likidite ve kayma hesabı
- Sadece tahmini pozitif komisyon-sonrası farkta sanal işlem kaydı
- Sanal bakiye grafiği, günlük, Türkçe panel, API hatalarında bir tekrar denemesi

## Sabit sınırlar
- Başlangıç sanal bakiyesi: **1.000 USDT**
- İşlem başına en fazla **10 USDT (başlangıç sermayesinin %1'i)**
- Maksimum hesaplanan kayma: **%2**
- Varsayılan komisyon varsayımı: **her taraf için %0,1** (gerçek borsa tarifesi değildir)
- **Gerçek API emri, özel anahtar, cüzdan, transfer, para çekme yok**

## Önemli sınırlamalar
- Paneldeki 8 isim, tamamen entegre bağımsız AI/Grok ajanları anlamına gelmez. Balina takibi ve Hype entegrasyonu henüz yok.
- Solana tokenleri üzerinde sanal işlem yapılmaz. Mint, freeze, LP kilidi, honeypot ve rug-pull güvenlik kontrolleri henüz yoktur.
- Borsalar arası varsayımsal alım/satım, iki borsada varlıkların önceden bulunduğunu ve iki işlemin birlikte gerçekleştiğini varsayar. Gerçek gecikme, minimum emir, rebalancing ve transfer giderleri dahil değildir.
- Fiyatlar farklı anlarda gelir; gösterilen fiyat farkları **gerçek arbitraj kârı değildir**.
- Otomatik tarama yalnızca uygulama oturumu aktifken çalışır; ücretsiz Streamlit sunucusu uyuyabilir. **7/24 daemon yoktur**.
- Günlük yalnızca oturum belleğindedir, yeniden başlatma/oturum kapanması halinde kaybolabilir.
- Bu bir yatırım tavsiyesi veya test edilmiş kârlı strateji değildir.

## iPhone / Streamlit Cloud
1. https://share.streamlit.io/ sayfasında GitHub ile oturum aç.
2. Repo: `aionexofficial/crypto-8-agent-bott`, branch: `main`, main file: `app.py`.
3. Uygulamayı aç, `Otomatik tarama` ve isteğe bağlı `Varsayımsal arbitraj simülasyonu` anahtarlarını etkinleştir.
4. Safari üzerinden ana ekrana ekleyebilirsin.

No passwords, seed phrases, private keys or API secrets should be committed.
