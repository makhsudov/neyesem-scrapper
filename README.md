> **Not:** Şu an yalnızca `getir_yemek` scraper'ı çalışmaktadır.

# Kurulum

```bash
pip install -r requirements.txt
playwright install chromium   # sadece --discover için
```

---

# Çalıştırma

```bash
# Tek şehir
python main.py --cities bursa

# Birden fazla şehir
python main.py --cities istanbul ankara izmir bursa antalya

# Sıfırdan (cache yok say)
python main.py --cities bursa --no-incremental

# API endpoint'ini otomatik keşfet, sonra çek
python main.py --discover --cities bursa

# API URL'sini manuel belirt (keşif başarısız olursa)
python main.py --discover --api-url https://... --cities bursa
```

---

# Çıktı Yapısı

```
output/
  bursa/
    getir_yemek/
      pizza-hut-osmangazi.json     ← bir restoran + menü
      ahiska-mantisi-osmangazi.json
  istanbul/
    getir_yemek/
      ...
```

Her JSON dosyası: `source`, `scraped_at` + tüm restoran alanları + `menu.categories[].items[]`

---

# Fiyat Karşılaştırması

```bash
python compare.py bursa getir_yemek yemeksepeti
```

Aynı şehirde iki kaynağı isim benzerliğiyle eşleştirir, fiyat farklılıklarını gösterir.

---

# Yeni Servis Ekleme

1. `scrapers/yemeksepeti.py` oluştur, `BaseScraper`'ı genişlet:

```python
from scrapers.base_scraper import BaseScraper

class YemeksepeteScraper(BaseScraper):

    @property
    def source_name(self) -> str:
        return "yemeksepeti"

    def _get_headers(self) -> dict: ...
    def fetch_restaurants(self, lat, lng, city="") -> list: ...
    def fetch_menu(self, restaurant) -> Restaurant: ...
```

2. `main.py` içindeki `SCRAPERS` sözlüğüne ekle:

```python
SCRAPERS = {
    "getir_yemek": GetirYemekScraper,
    "yemeksepeti": YemeksepeteScraper,
}
```

3. Çalıştır:

```bash
python main.py --sources yemeksepeti --cities bursa
```
