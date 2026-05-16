```markdown
**Not:** Şu an yalnızca `getir_yemek` scraper'ı çalışmaktadır.

# Kurulum

```bash
pip install -r requirements.txt
playwright install chromium    # sadece --discover için gerekli
```

---

# Çalıştırma

```bash
# Tek şehir
python main.py --sources getir_yemek --cities bursa

# Birden fazla şehir
python main.py --sources getir_yemek --cities istanbul ankara izmir bursa antalya

# Sıfırdan yeniden çek (cache'i yok say)
python main.py --sources getir_yemek --cities bursa --no-incremental

# API endpoint'ini otomatik keşfet
python main.py --discover --sources getir_yemek --cities bursa

# API URL'sini manuel belirt
python main.py --discover --sources getir_yemek --api-url https://... --cities bursa
```

---

# Çıktı Yapısı

```
output/
  bursa/
    getir_yemek/
      pizza-hut-osmangazi.json
      ahiska-mantisi-osmangazi.json
      ...
  istanbul/
    getir_yemek/
      ...
```

Her JSON dosyası restoran bilgileri ve tam menüyü içermektedir.
```

---
