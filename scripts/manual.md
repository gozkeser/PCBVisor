# Fiducial Finder v1.00 — El Kitabı

## 1. Genel Amaç

**Fiducial Finder**, PNG formatındaki görüntülerde eşmerkezli (konsantrik) daire çiftlerini tespit etmek için geliştirilmiş bir komut satırı aracıdır.  
Kontör analizi ve dairesellik (circularity) filtrelemesi kullanarak iki aşamalı (dual-pass) bir arama gerçekleştirir.  
Tespit edilen eşmerkezli çiftlerin **iç dairelerini** işaret (fiducial) olarak tanımlar ve bu işaretçilerin özelliklerini bir JSON metadata dosyasına aktarır.  
Hata ayıklama modunda (`--debug`), ara adımlara ait gri tonlama ve kenar görüntüleri de üretilir.

Script, tespit parametrelerini bir **JSON yapılandırma dosyasından** okur; yapılandırma dosyası sağlanmadığında varsayılan parametreler kullanılır.

---

## 2. Özellikler

| Özellik | Açıklama |
|---|---|
| **PNG Girdi Desteği** | Yalnızca `.png` uzantılı dosyaları işler. |
| **JSON Yapılandırma** | Tüm tespit parametreleri harici bir JSON dosyasından okunabilir. |
| **Varsayılan Parametreler** | Yapılandırma dosyası sağlanmazsa yerleşik varsayılan değerler kullanılır. |
| **İki Aşamalı Tarama (Dual-Pass)** | Önce dış büyük daireler (Pass 1), ardından iç küçük daireler (Pass 2) taranır. |
| **Dairesellik Filtreleme** | `4π A / P²` formülü ile hesaplanan dairesellik değerine göre eleme yapılır. |
| **Canny Kenar Algılama** | Eşik değeri yapılandırılabilir; alt eşik = üst eşik / 2 olarak alınır. |
| **Gürültü Azaltma** | 5×5 medyan bulanıklaştırma (median blur) uygulanır. |
| **Merkez Çakıştırma** | Dış ve iç daire adaylarının merkezleri arasındaki Öklid mesafesi, belirlenen tolerans değerine göre eşleştirilir. |
| **Tekilleştirme (Deduplication)** | Canny'nin iç/dış sınırlarından kaynaklanan yakın tespitler, konum ve yarıçap toleransına göre tekil hale getirilir. |
| **Hata Ayıklama (Debug) Modu** | `--debug` ile her ara adımın görsel çıktısı kaydedilir (steps 2–6). |
| **Çift Yönlü Loglama (Dual Logger)** | Terminal çıktısı eş zamanlı olarak hem ekrana yazılır hem de bir `.txt` log dosyasına kaydedilir. ANSI renk kodları log dosyasından temizlenir. |
| **Renkli Terminal Çıktısı** | Önemli bilgiler sarı, camgöbeği, kırmızı ve beyaz renklerle vurgulanır. |
| **Anotasyonlu Görüntü** | Tespit edilen eşmerkezli çiftlerin sınırları (yeşil), merkez noktaları (kırmızı) ve ID etiketleri (mavi) çizilmiş bir PNG çıktısı üretilir. |
| **JSON Metadata Çıktısı** | Her işaretçi için merkez koordinatları, yarıçap, çap ve dış daire partnerine ait bilgileri içeren yapılandırılmış JSON dosyası oluşturulur. |

---

## 3. Algoritma Aşamaları (Pipeline)

Script aşağıdaki adımları sırayla gerçekleştirir:

### Aşama 1 — Yapılandırma Yükleme
- Kullanıcı tarafından sağlanan JSON yapılandırma dosyası okunur.
- Dosya yoksa veya JSON geçersizse hata üretilir.
- Zorunlu anahtarların varlığı kontrol edilir.
- Yapılandırma dosyası sağlanmazsa `DEFAULT_PARAMS` kullanılır.

### Aşama 2 — Görüntü Okuma
- Girdi dosyası diskte kontrol edilir.
- OpenCV (`cv2.imread`) ile görüntü yüklenir.
- Dosya PNG değilse veya okunamazsa hata üretilir.

### Aşama 3 — Ön İşleme (Preprocessing)
Bu aşama, `process_and_save_intermediates()` metodu ile gerçekleştirilir:

| Alt Adım | İşlem | Debug Çıktısı |
|---|---|---|
| **Step 2** | BGR → Gri Tonlama (Grayscale) | `{dosya}_step2_out.png` |
| **Step 3** | 5×5 Medyan Bulanıklaştırma (Gürültü Azaltma) | `{dosya}_step3_out.png` |
| **Step 4** | Canny Kenar Algılama (Eşik: `canny_threshold/2` ↔ `canny_threshold`) | `{dosya}_step4_out.png` |

### Aşama 4 — Pass 1: Dış Daire Arama (Outer Circle)
- `detect_circles_pass()` ile büyük yarıçaplı (varsayılan: 32–36 px) ve yüksek dairesellikli kontörler taranır.
- Tüm kontörler `RETR_LIST` modu ile bulunur.
- Her kontör için alan, çevre ve dairesellik (`4π A / P²`) hesaplanır.
- Dairesellik eşiği (`outer_circle_min_circularity`) ve yarıçap aralığına göre filtreleme yapılır.
- Bulunan daire adayları `_deduplicate()` ile tekil hale getirilir.
- Debug modunda: **Step 5** çıktısı — tespit edilen dış daireler yeşil çerçeve ve kırmızı merkez noktası ile görselleştirilir.

### Aşama 5 — Pass 2: İç Daire Arama (Inner Circle)
- Aynı `detect_circles_pass()` mekanizması, küçük yarıçaplı (varsayılan: 14–18 px) daireler için çalıştırılır.
- Dairesellik eşiği (`inner_circle_min_circularity`) ve yarıçap aralığına göre filtreleme yapılır.
- Bulunan daire adayları `_deduplicate()` ile tekil hale getirilir.
- Debug modunda: **Step 6** çıktısı — tespit edilen iç daireler yeşil çerçeve ve kırmızı merkez noktası ile görselleştirilir.

### Aşama 6 — Eşmerkezli Eşleştirme (Concentric Pairing / Step 8)
- Her dış daire (Pass 1) ile her iç daire (Pass 2) arasındaki Öklid mesafesi hesaplanır.
- Mesafe `concentric_tolerance` değerinden küçük veya eşitse, bu iki daire **eşmerkezli çift** olarak kaydedilir.
- Bir daire yalnızca bir çifte atanabilir (eşsiz eşleme).
- Çiftteki küçük yarıçaplı daire **iç daire (inner)**, büyük yarıçaplı daire **dış daire (outer)** olarak etiketlenir.
- Debug modunda: Eşleştirme detayları (daire indeksleri, merkez koordinatları, yarıçaplar, ofset mesafesi) tablo halinde yazdırılır.

### Aşama 7 — Anotasyon ve Çıktı Dosyaları
- **Anotasyonlu Görüntü**: `{dosya}_annotated.png`
  - Her eşmerkezli çiftin iç ve dış daire sınırları yeşil renkte çizilir.
  - Merkez noktaları kırmızı ile işaretlenir.
  - İç daire merkezinin yanına mavi renkte benzersiz bir ID numarası yazılır.
- **JSON Metadata**: `{dosya}_fiducials.json`
  - Her işaretçi (fiducial) için:
    - `fiducial_id`: Benzersiz numara
    - `center_x`, `center_y`: Merkez koordinatları (3 ondalık)
    - `radius_px`, `diameter_px`: Yarıçap ve çap (piksel)
    - `outer_concentric_partner`: Dış daire bilgisi (merkez, yarıçap, çap, ofset)
- **Log Dosyası**: `{dosya}_log.txt` — Tüm terminal çıktısının ANSI koddan arındırılmış kopyası.

---

## 4. Kullanım

### 4.1. Gereksinimler
- Python 3.8+
- OpenCV (`cv2`)
- NumPy (`numpy`)

Gerekli kütüphaneleri yüklemek için:

```bash
pip install opencv-python numpy
```

### 4.2. Çalıştırma

```bash
python fid_finder_v1.00.py -i <girdi_dosyasi.png> [seçenekler]
```

### 4.3. Komut Satırı Argümanları

| Argüman | Kısa | Zorunlu | Varsayılan | Açıklama |
|---|---|---|---|---|
| `--input` | `-i` | Evet | — | İşlenecek PNG dosyasının yolu. |
| `--output-dir` | `-o` | Hayır | Girdi dosyasının bulunduğu dizin | Tüm çıktı dosyalarının kaydedileceği dizin. |
| `--config` | `-c` | Hayır | Varsayılan parametreler | JSON yapılandırma dosyasının yolu. |
| `--debug` | — | Hayır | Kapalı | Ara adım görüntülerini ve detaylı log çıktısını etkinleştirir. |

### 4.4. Örnek Kullanımlar

**Temel kullanım (varsayılan parametrelerle):**
```bash
python fid_finder_v1.00.py -i ornek.png
```

**Özel çıktı dizini ile:**
```bash
python fid_finder_v1.00.py -i ornek.png -o ./sonuclar
```

**Yapılandırma dosyası ile:**
```bash
python fid_finder_v1.00.py -i ornek.png -c config.json
```

**Hata ayıklama modu ile:**
```bash
python fid_finder_v1.00.py -i ornek.png --debug
```

**Tüm seçenekler bir arada:**
```bash
python fid_finder_v1.00.py -i ornek.png -o ./sonuclar -c config.json --debug
```

---

## 5. Yapılandırma Dosyası (JSON)

`config.json` dosyası aşağıdaki 8 anahtarı içermelidir:

```json
{
    "canny_threshold": 100.0,
    "inner_circle_min_circularity": 0.75,
    "inner_circle_min_radius": 14,
    "inner_circle_max_radius": 18,
    "outer_circle_min_circularity": 0.75,
    "outer_circle_min_radius": 32,
    "outer_circle_max_radius": 36,
    "concentric_tolerance": 1.0
}
```

| Parametre | Tip | Varsayılan | Açıklama |
|---|---|---|---|
| `canny_threshold` | float | 100.0 | Canny kenar algılama üst eşiği. Alt eşik = üst eşik / 2. |
| `inner_circle_min_circularity` | float | 0.75 | İç daire adayları için minimum dairesellik değeri (0–1 arası). |
| `inner_circle_min_radius` | int | 14 | İç daire adayları için minimum yarıçap (piksel). |
| `inner_circle_max_radius` | int | 18 | İç daire adayları için maksimum yarıçap (piksel). |
| `outer_circle_min_circularity` | float | 0.75 | Dış daire adayları için minimum dairesellik değeri (0–1 arası). |
| `outer_circle_min_radius` | int | 32 | Dış daire adayları için minimum yarıçap (piksel). |
| `outer_circle_max_radius` | int | 36 | Dış daire adayları için maksimum yarıçap (piksel). |
| `concentric_tolerance` | float | 1.0 | İç ve dış daire merkezleri arasındaki maksimum izin verilen Öklid mesafesi (piksel). |


---

## 6. Çıktı Dosyaları

Script başarıyla çalıştığında aşağıdaki dosyalar üretilir:

| Dosya | Açıklama |
|---|---|
| `{dosya}_annotated.png` | Tespit edilen eşmerkezli çiftlerin işaretlenmiş görüntüsü. |
| `{dosya}_fiducials.json` | Her işaretçinin koordinat, yarıçap ve eşleşme bilgilerini içeren JSON dosyası. |
| `{dosya}_log.txt` | Tüm terminal çıktısının ANSI kodlarından arındırılmış log dosyası. |

Debug modu etkinken (`--debug`) ek olarak:

| Dosya | Açıklama |
|---|---|
| `{dosya}_step2_out.png` | Gri tonlamalı (grayscale) görüntü. |
| `{dosya}_step3_out.png` | Medyan bulanıklaştırma (median blur) sonrası görüntü. |
| `{dosya}_step4_out.png` | Canny kenar algılama sonrası ikili (binary) kenar görüntüsü. |
| `{dosya}_step5_out.png` | Pass 1 — tespit edilen dış daire adaylarının görselleştirilmesi. |
| `{dosya}_step6_out.png` | Pass 2 — tespit edilen iç daire adaylarının görselleştirilmesi. |

---

## 7. Hata Yönetimi

Script aşağıdaki durumlarda hata mesajı verir ve çıkış yapar:

| Hata Türü | Durum | Çıkış Kodu |
|---|---|---|
| **Yapılandırma Hatası** | Yapılandırma dosyası bulunamazsa, JSON geçersizse veya zorunlu anahtarlar eksikse. | 1 |
| **Dosya Sistemi Hatası** | Girdi dosyası bulunamazsa veya dosya yazılamazsa. | 1 |
| **Veri Doğrulama Hatası** | Girdi PNG formatında değilse veya görüntü çözülemezse. | 1 |
| **Yazma Hatası** | Görüntü veya JSON dosyası yazılamazsa. | 1 |
| **Beklenmeyen Hata** | Yukarıdakiler dışında kritik bir hata oluşursa. | 1 |

---

## 8. Teknik Detaylar

### Dairesellik (Circularity) Hesabı

```
Circularity = (4 * π * Alan) / (Çevre²)
```

- **1.0** → mükemmel daire
- **0.0** → şekilsiz kontör
- Varsayılan eşik: **0.75** (hem iç hem dış daireler için)

### Canny Eşik Değerleri

```
alt eşik = canny_threshold / 2
üst eşik = canny_threshold
```

### Tekilleştirme (Deduplication)

Yakın tespitler aşağıdaki kriterlere göre tekil hale getirilir:
- Merkezler arası uzaklık < 3.0 piksel (spatial_tolerance)
- Yarıçap farkı < 3.0 piksel (radius_tolerance)

### Eşmerkezli Eşleştirme

Her dış daire adayı ile her iç daire adayı arasındaki Öklid mesafesi:
```
distance = √((x₁ - x₂)² + (y₁ - y₂)²)
```
- `distance ≤ concentric_tolerance` ise eşleşme başarılı.
- Bir daire yalnızca bir eşleşmede kullanılabilir (birebir eşleme).

---

## 9. Sürüm Bilgisi

- **Sürüm:** 1.00
- **Son Güncelleme:** 03.07.2026
- **Yazar:** G.OZKESER

---

## 10. Örnek Kullanım Senaryosu

**Adım adım tipik bir kullanım:**

1. Girdi görüntüsünü hazırlayın (örneğin: `PCB_MARKER.png`).
2. Gerekirse parametreleri ayarlayın (`config.json`).
3. Scripti çalıştırın:
   ```bash
   python fid_finder_v1.00.py -i PCB_MARKER.png -o ./cikti --debug
   ```
4. Terminal çıktısını inceleyin:
   - Aktif parametreler listelenir.
   - Her aşamanın ilerlemesi görüntülenir.
   - Tespit edilen işaretçi sayısı raporlanır.
5. Çıktı dosyalarını inceleyin:
   - `PCB_MARKER_annotated.png` — anotasyonlu görüntü
   - `PCB_MARKER_fiducials.json` — metadata
   - `PCB_MARKER_log.txt` — log dosyası
   - `cikti/` altındaki debug görüntüleri

---

## 11. Sık Karşılaşılan Sorunlar

| Sorun | Olası Neden | Çözüm |
|---|---|---|
| Hiçbir işaretçi bulunamadı | Yarıçap aralıkları görüntüdeki dairelere uygun değil | `config.json`'daki min/max yarıçap değerlerini ayarlayın |
| Çok fazla yanlış tespit | Dairesellik eşiği çok düşük | `min_circularity` değerini artırın (örn. 0.85) |
| Eşleşme bulunamadı | Merkez toleransı çok dar | `concentric_tolerance` değerini artırın |
| Kenarlar algılanamıyor | Canny eşiği çok yüksek veya düşük | `canny_threshold` değerini değiştirin |
| Debug çıktıları oluşmuyor | `--debug` bayrağı kullanılmamış | Komuta `--debug` ekleyin |

---

*Bu doküman `fid_finder_v1.00.py` scripti için hazırlanmıştır. Scriptin kaynak kodu incelenerek otomatik oluşturulmuştur.*