<p align="center">
  <img src="https://raw.githubusercontent.com/haskaan/ha-flydigi-cooler/main/custom_components/flydigi_cooler/brand/icon@2x.png" alt="Flydigi Cooler" width="200">
</p>

<h1 align="center">Flydigi Cooler — Home Assistant entegrasyonu</h1>

<p align="center">
  <a href="https://hacs.xyz"><img alt="HACS" src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg"></a>
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-2024.6%2B-41BDF5.svg">
  <a href="https://github.com/haskaan/ha-flydigi-cooler/releases"><img alt="Release" src="https://img.shields.io/github/v/release/haskaan/ha-flydigi-cooler?label=release&sort=semver"></a>
</p>

<p align="center">
  <a href="https://analytics.home-assistant.io/"><img alt="HA installs" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&amp;query=%24.flydigi_cooler.total&amp;label=HA%20installs&amp;color=41BDF5&amp;logo=home-assistant&amp;logoColor=white"></a>
  <a href="https://github.com/haskaan/ha-flydigi-cooler/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/haskaan/ha-flydigi-cooler.svg?logo=github"></a>
  <a href="https://github.com/haskaan/ha-flydigi-cooler/issues"><img alt="Issues" src="https://img.shields.io/github/issues/haskaan/ha-flydigi-cooler.svg"></a>
  <a href="https://github.com/haskaan/ha-flydigi-cooler/actions/workflows/validate.yml"><img alt="Validate" src="https://img.shields.io/github/actions/workflow/status/haskaan/ha-flydigi-cooler/validate.yml?label=validate"></a>
</p>

<p align="center">
  <b>Flydigi BS2 / BS2 Pro / BS3 / BS3 Pro</b> laptop soğutucuları için entegrasyon.<br>
  Fanı, mod ve seviyeleri, RGB ışığı ve cihaz ayarlarını Bluetooth LE üzerinden kontrol edin.
</p>

<p align="center">
  <sub><b>Resmî olmayan topluluk projesi.</b> Flydigi ile bağlantılı, onun tarafından desteklenen veya
  onaylanan bir proje değildir. "Flydigi" ilgili sahibinin ticari markasıdır ve burada yalnızca
  entegrasyonun çalıştığı donanımı tanımlamak için kullanılmıştır. Topluluk tarafından tersine
  mühendislikle çözülmüş bir protokole dayanır — kendi riskinizde kullanın.</sub>
</p>

<p align="center">
  İşinize yaradıysa GitHub'da ⭐ vermeyi unutmayın.
  <br>
  <sub><i>English documentation: <a href="README.md">README.md</a></i></sub>
</p>

---

## Kurulum

### Seçenek 1. HACS ile (önerilen)

1. HACS kurulu değilse [HACS](https://hacs.xyz) kurun.
2. HACS → Entegrasyonlar → ⋮ → **Özel depolar**.
3. `https://github.com/haskaan/ha-flydigi-cooler` adresini **Integration**
   kategorisiyle ekleyin.
4. HACS entegrasyon sayfasında **Flydigi Cooler** araması yapıp kurun.
5. Home Assistant'ı yeniden başlatın.

> Flydigi Cooler henüz HACS varsayılan deposunda değil, bu yüzden 3. adım
> gerekiyor. Depo varsayılan listeye kabul edildiğinde bu adım kalkar ve
> doğrudan arama yeterli olur.

### Seçenek 2. Elle

1. HA yapılandırma dizinini açın (`configuration.yaml` dosyasının bulunduğu dizin).
2. `custom_components` dizini yoksa oluşturun.
3. `custom_components` içinde `flydigi_cooler` adında yeni bir klasör oluşturun.
4. Bu depodaki `custom_components/flydigi_cooler/` dizinindeki tüm dosyaları indirin.
5. İndirdiğiniz dosyaları oluşturduğunuz klasöre kopyalayın.
6. Home Assistant'ı yeniden başlatın.

### Cihazı ekleme

**Ayarlar → Cihazlar ve Hizmetler → Entegrasyon Ekle → Flydigi Cooler.**

Cihaz pairing modunda reklam veriyorsa **Keşfedildi** kartından onaylayın.
Keşif görünmezse açılan listeden keşfedilen cihazı seçin; listede yoksa
Bluetooth adresini elle girin.

Aynı entegrasyonla **birden fazla Flydigi soğutucu** eklenebilir (ör. BS3 Pro
ve BS2 Pro). Her cihaz kendi config entry'si ve entity'leriyle gelir. Model adı
önce Bluetooth reklamındaki isimden (`FlyDigi BS2PRO`, `FlyDigi BS3PRO` vb.),
isim yoksa cihazın Device Information servisindeki model numarasından okunur;
cihazı ayrıca yeniden adlandırmanız gerekmez.

## Gereksinimler

- Home Assistant 2024.6+ (Bluetooth entegrasyonu kurulu ve çalışıyor olmalı)
- Cihazın menzil içinde ve **açık** olması
- Cihaz başka bir cihaza (ör. Flydigi Space Station çalışan laptop) bağlı **olmamalı**

> BLE çevresel cihazlar genelde tek bağlantı kabul eder. Aynı anda hem Windows
> uygulaması hem Home Assistant bağlanamaz. Home Assistant'ı kullanırken
> Flydigi Space Station'ı kapatın (veya o laptopun Bluetooth'unu kapatın).

## Ne yapar

| Platform | Entity | Açıklama |
| --- | --- | --- |
| `fan` | Ana fan | Aç/kapat, % hız (gerçek zamanlı RPM), mod seçimi (Silent / Standart / Strong / Overclock) |
| `select` | Seviye | Aktif modun 3 hız seviyesinden biri (`1` / `2` / `3`) |
| `select` | Akıllı durma | PC kapanınca fanın davranışı (`Kapalı` / `Anında` / `Gecikmeli`; `0x0D`) |
| `switch` | Kademe ışığı | Cihazdaki 4 kademe LED'i (`0x48`) |
| `switch` | Güçte otomatik başlat | Elektrik gelince fan kendiliğinden çalışsın (`0x0C`) |
| `light` | Işık | RGB aç/kapat + efekt, parlaklık ve renk |
| `number` | Işık hızı | Animasyon hızı (0 yavaş – 100 hızlı) |
| `sensor` | Anlık devir | Cihazın ölçtüğü RPM |
| `sensor` | Hedef devir | Cihazın hedeflediği RPM |
| `sensor` | Kontrol modu | `Sabit kademe` / `Gerçek zamanlı` |
| `sensor` | Seçili kademe | Aktif mod adı (Silent / Standart / Strong / Overclock); ham kademe `gear` özniteliğinde |
| `sensor` | Yazılım sürümü | Örn. `0.0.2.4` |

> Görünen adlar Home Assistant arayüz diline göre çevrilir (`en` / `tr`).
> Entity ID'leri her zaman İngilizce kalır (`current_rpm`, `control_mode` vb.),
> böylece arayüz dilini değiştirmek otomasyonları bozmaz.

### Modlar ve seviyeler

Fan kartındaki 4 mod ve `select.flydigi_bs3_pro_level` entity'si ile seçilen
3 seviye:

| Mod | Seviye 1 | Seviye 2 | Seviye 3 |
| --- | ---: | ---: | ---: |
| Silent | 1300 | 1700 | 1900 |
| Standart | 2100 | 2400 | 2700 |
| Strong | 2900 | 3000 | 3300 |
| Overclock | 3400 | 3700 | 4000 |

Seviyeler cihazın sabit kademe tablosuna yazılmaz; **gerçek zamanlı RPM** olarak
uygulanır (flash yazımı yok). Cihazın kendi düğmesiyle seçilen kademeler aynı
mod adlarına eşlenir: Gear 1 = Silent, Gear 2 = Standart, Gear 3 = Strong,
Gear 4 = Overclock. Düğmeyle bir kademe seçilirse seviye, o kademenin RPM'ine
karşılık gelen seviyeye ayarlanır (ör. Gear 2 → Standart 3).

> **Her mod kendi seviyesini hatırlar.** Silent 2 seçip Strong'a geçersen,
> yeniden Silent'a döndüğünde **2** kalır. Seçimler `.storage`'a yazılır, HA
> yeniden başlasa da korunur. Bu yüzden otomasyonlarda **önce `fan.set_preset_mode`
> (mod), sonra `select.select_option` (seviye)** kullanın; seviye, o anki moda
> kaydedilir.

Mevcut sabit kademeler cihazdan okunur (bu ünitede gözlenen:
1300 / 2700 / 3000 / **4000** RPM; yüzde hesabı en yüksek kademeyi üst sınır
alır).

Cihaz saniyede bir durum bildirimi (`0xEF`) gönderir; entegrasyon bunları
en fazla 3 saniyede bir entity'lere yansıtır (30 s'lik yoklama yedek olarak
kalır). Fan kapatıldığında **hedef devir 0** olur ve fan "kapalı" sayılır;
cihaz birkaç saniye son ölçülen devri bildirmeye devam etse bile anlık devir
0 gösterilir (toggle'ın kendiliğinden geri açılmasını önler).

Fan kapalıyken tekrar açıldığında **son mod geri gelir**: kapatmadan önce
bir mod/seviye seçiliyse aynı mod ve seviye (ör. Standart 2 → 2400 RPM),
yüzde modundaysa aynı hedef RPM (ör. %60 → 2720 RPM). Seçim `.storage`'a
yazılır, HA yeniden başlasa da hatırlanır. Cihazın kendi düğmesiyle kademe
değiştirirsen bu da izlenir. Fan kapalıyken de kart son modu ve seviyeyi
**seçili** gösterir; yüzde modunda ön ayar/seviye seçili görünmez (açınca
yüzde geri gelir).

### Işık (RGB)

`light.flydigi_bs3_pro_light` — aç/kapat, parlaklık, renk ve efekt seçimi.
Aç/kapat `0x46` ile yapılır (LED çıkışını açan/kapatan tek komut; `0x44` yalnızca
animasyon seçer). Efektler cihaza bir **program** olarak yüklenir
(`0x41` init → 19 × `0x47` kare → `0x43` commit); firmware kareler arasında
kendisi interpolasyon yapar.

| Efekt | Davranış |
| --- | --- |
| Static | Tek renk, sabit |
| Multi color | Kırmızı / yeşil / mavi üç renk sabit |
| Rotation | Seçili renkte dönen tek nokta |
| Flowing | Altı renkli gökkuşağı akışı |
| Breathing | Seçili renkte nefes alma |

Parlaklık firmware tarafından uygulanır (0–100). `0x43` commit her efekt
değişiminde bir flaş sayfası siler. Efekt, renk ve parlaklık `.storage`'da
saklanır; **fan açılınca ışık her zaman açılır** ve hatırlanan efekt yeniden
yüklenir (cihaz PC ile birlikte güç kaybedince RAM'deki program sıfırlanır).
Işık zaten yanıyorsa ve parametreler değişmediyse komut gönderilmez.
**Fan kapanınca ışık da kapanır.**

> Işık modu hafızası entegrasyonun kendi `.storage` dosyasındadır; HA veya
> entegrasyon yeniden kurulsa da korunur, ancak entegrasyonu tamamen kaldırıp
> yeniden eklersen varsayılan (Static/beyaz) ile başlar.

Animasyon hızı `number.flydigi_bs3_pro_light_speed` ile 0–100 arasında
ayarlanır (100 = hızlı, 0 = yavaş; resmî uygulamadaki "Speed" ile aynı ölçek).
Hız değişince efekt yeni hızla yeniden yüklenir.

### Cihaz ayarları (flash)

Bu üç ayar cihazın kendi flaşına yazılır; HA kapalıyken de geçerli kalır. Her
yazma bir flaş sayfası siler, bu yüzden entegrasyon komutu **yalnızca değer
gerçekten değiştiğinde** ve **yalnızca siz elle değiştirdiğinizde** gönderir.

| Entity | Komut | Davranış |
| --- | --- | --- |
| `select.flydigi_bs3_pro_smart_stop` | `0x0D` | **Kapalı:** özellik devre dışı. **Anında:** PC kapanınca fan hemen durur. **Gecikmeli:** PC kapandıktan sonra bir süre daha çalışıp içerideki sıcak havayı tahliye eder (soğutucu güç almaya devam etmelidir). |
| `switch.flydigi_bs3_pro_gear_light` | `0x48` | RGB şeridin üstündeki 4 kademe LED'ini açar/kapatır. |
| `switch.flydigi_bs3_pro_power_on_start` | `0x0C` | Cihaza elektrik geldiği anda (akıllı priz, dock) tuşa basmadan son modla çalışmaya başlar. |

- **HA yeniden başlarken veya yeniden bağlanırken bu komutların hiçbiri
  gönderilmez.** Açılışta yalnızca `0x23` / `0x21` / `0x08` (gerçek zamanlı RPM
  ve kademe) kullanılır; bunlar flaşa yazmaz.
- Akıllı durma modu cihazdan `0xEF` bildirimiyle okunur (2. bayt, bitler `0x0E`),
  yani select her zaman donanımın gerçek değerini gösterir — bunun için yazma
  gerekmez. Kademe ışığı ve güçte başlatma cihaz tarafından bildirilmez; son
  değer `.storage`'da saklanır ve optimistic olarak işaretlenir.
- `0x48` firmware tarafından karşılaştırılmaz: aynı değeri tekrar göndermek bile
  bir flaş sayfası siler. Entegrasyon bu yüzden değeri önbelleğe alır ve aynı
  değeri göndermez. `0x0C` / `0x0D` ise firmware tarafında karşılaştırılır.

## Eşleştirme (pairing) ve adres değişimi

Cihazın ayrı bir pairing düğmesi yoktur. Kullanım kılavuzundaki tek yöntem:

> Güç düğmesine **10 saniye** basılı tutun — vites göstergesi yanıp söner ve
> Bluetooth eşleşme bilgisi silinir. Cihaz bu andan sonra yeni bağlantı kabul eder.

Bu işlem, cihazın daha önce eşleştiği merkezi (ör. Windows laptop) unutmasını
sağlar. Cihaz bir merkeze eşleşmişken diğer merkezlerin bağlantı isteklerini
**link seviyesinde yanıtsız bırakır**; HCI logunda bu, `LE Connection Complete`
sonrası `0x3E Connection Failed to be Established` olarak görünür.

Ayrıca cihaz, bazı açılışlarda **rastgele statik BLE adresi** üretir
(gözlemlediğimiz: `DD:7F:64:2D:BA:83` → `DE:7F:64:2D:BA:83`). Bu yüzden
entegrasyon sabit adrese güvenmez: önce reklamda görülen isim (`FlyDigi BS3PRO`)
veya `FFF0` servisiyle cihazı bulur, bulamazsa kayıtlı adresi dener. Adres
değişse bile ek bir işlem gerekmez.

Başarılı her bağlantıda adres `.storage/flydigi_cooler.<entry_id>` dosyasına
yazılır ve HA yeniden başladığında **ilk olarak o adres** denenir. Bu önemli:
cihaz normal çalışırken reklamında isim/`FFF0` yayınlamıyor (loglarda
`advertised=[]`), isim yalnızca eşleştirme modunda görünüyor. Adres yine de
değişirse güç düğmesine 10 s basıp eşleştirme moduna alın; HA cihazı isimle
bulup yeni adresi kendisi kaydeder.

## Cihazın 2 dakikalık zaman aşımı

BS3 Pro, gerçek zamanlı moddan (0 RPM dahil) ~2 dakika sonra kendiliğinden
seçili sabit kademeye döner. Entegrasyon hem kapalıyken 0 RPM'i hem de bir
mod/seviye veya yüzde etkinken hedef RPM'i 60 saniyede bir tazeler (çalışma
zamanı komutu, flash yazımı yok). Böylece Silent / Standart / Strong /
Overclock seçimi ve yüzde hızı cihazın kendiliğinden düşmesine rağmen korunur.

## Protokol özeti (meraklısına)

```
5A A5 <CMD> <LEN> <PAYLOAD...> <CHECKSUM>
LEN      = 2 + payload uzunluğu
CHECKSUM = (CMD + LEN + payload baytları) & 0xFF
```

Transport, cihazın özel GATT servisi üzerinden yürür — HID katmanı gerekmez:

| | UUID |
| --- | --- |
| Servis | `0000fff0-0000-1000-8000-00805f9b34fb` |
| Yazma | `0000fff2-0000-1000-8000-00805f9b34fb` |
| Bildirim | `0000fff1-0000-1000-8000-00805f9b34fb` |

Kullanılan komutlar:

| CMD | Anlam |
| --- | --- |
| `0x21` | Gerçek zamanlı hedef RPM (`rpm_lo rpm_hi`) |
| `0x22` | RPM sorgusu |
| `0x23` / `0x24` | Gerçek zamanlı moda gir / çık |
| `0x25` | Çalışma modu sorgusu |
| `0x27` | Kademe RPM tablosu |
| `0x08` | Sabit kademe seç (flash'a yazmaz) |
| `0x0C` | Güçte otomatik başlatma (flash) |
| `0x0D` | Akıllı durma modu: 0 kapalı / 1 anında / 2 gecikmeli (flash) |
| `0x48` | Kademe ışığı LED'leri (flash, değer karşılaştırılmaz) |
| `0xEF` | Cihazdan durum bildirimi (1 sn'de bir) |

Bildirimler birden fazla çerçeve içerebilir veya çerçeve iki bildirime
bölünebilir; `protocol.FrameStream` bunu yeniden birleştirir.

Gönderilen her çerçeve, entegrasyon için `debug` günlük düzeyi açıkken
`tx 5a a5 …` olarak loglanır; böylece hangi komutun gittiği doğrulanabilir:

```yaml
logger:
  logs:
    custom_components.flydigi_cooler: debug
```

### Flash'a yazan komutlar

`0x26` (kademe RPM yazma), `0x46` (RGB aç/kapa), `0x48` (kademe ışığı), `0x43`
(RGB commit), `0x0C` (güçte başlatma) ve `0x0D` (akıllı durma) her çağrıda
cihazın **flaşına yazar**. `0x26` hiç kullanılmaz; kademe için yalnızca `0x08`
gönderilir (flaş yazmaz).

Kalanların hepsi değer değişmediyse gönderilmez: bilinen durum `.storage`'da
saklanır ve her setter önce "zaten bu değerde mi?" diye bakar. Hiçbiri açılışta,
yeniden bağlanmada veya yoklamada gönderilmez; yalnızca kullanıcı bir entity'yi
değiştirdiğinde tek bir çerçeve gider. `0x48`'de bu koruma zorunludur çünkü
firmware değeri karşılaştırmaz; `0x0C`/`0x0D`'de firmware aynı değeri görürse
zaten yazmaz.

## Otomasyonlar

Bu depo **otomasyon içermez**. Entegrasyon yalnızca entity'leri sağlar;
PC açık/kapalı algılama, BF6 modu gibi senaryoları kendi otomasyonlarınızla
kurun. Mod ve seviye iki ayrı adımdır:

```yaml
- action: fan.set_preset_mode
  target:
    entity_id: fan.flydigi_bs3_pro
  data:
    preset_mode: Overclock
- action: select.select_option
  target:
    entity_id: select.flydigi_bs3_pro_level
  data:
    option: "3"
```

## Teşekkür

Protokol bilgisi için:

- [chenqianhe/Flydigi-BS](https://github.com/chenqianhe/Flydigi-BS) — macOS BS3 kontrolcüsü, komut seti
- [TIANLI0/THRM](https://github.com/TIANLI0/THRM) — BS serisi için açık kaynak kontrol merkezi, ayrıntılı protokol dokümanı

## Yasal

Flydigi ile bağlantılı değildir. Kendi riskinizde kullanın. Cihazın flash'ına
yazan komutlar yalnızca elle değiştirdiğiniz ayarlar için ve değer gerçekten
değiştiğinde gönderilir; HA yeniden başladığında hiçbiri yazılmaz.

## Lisans

[MIT](LICENSE)
