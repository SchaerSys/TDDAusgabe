# Technisches Pruefprotokoll - https://www.tischlein-deckdich.at

Methodik: 5 Messungen je Seite (curl, GET), Auswertung als Mittelwert. Formulare wurden ausschliesslich im HTML-Quelltext analysiert - **es wurde kein Formular abgesendet, kein POST-Request ausgefuehrt, kein Datensatz und keine Mail ausgeloest.**

> **Hinweis zur Abgrenzung:** Core Web Vitals (LCP, CLS, INP) sind mit curl nicht messbar - sie erfordern eine Browser-Rendering-Messung. Diese Werte sind separat ueber PageSpeed Insights / CrUX zu ergaenzen. Die hier ausgewiesene TTFB ist jedoch die serverseitige Basis, die in LCP direkt eingeht.

> **Hinweis zur Messumgebung:** Die Messungen liefen ueber einen vorgeschalteten Proxy (Sandbox-Umgebung). Dadurch sind **nicht belastbar**: absolute TTFB-/Ladezeitwerte (enthalten Proxy- und Relay-Laufzeit), die ausgewiesene Server-IP (zeigt den lokalen Proxy) und die HTTP-Version (gilt zum Proxy, nicht zum Ursprungsserver). **Belastbar sind** alle inhaltlichen Befunde: HTML- und Formularanalyse, Antwort-Header (Cache-Control, Kompression, Security-Header), Ressourcengroessen sowie SEO- und Barrierefreiheitsmerkmale - diese reicht der Proxy unveraendert durch. Ebenso belastbar sind *Vergleiche innerhalb* dieses Berichts, da alle Seiten denselben Netzweg nutzen.

## 1. Performance (Serverseite)

| Seite | TTFB Ø | TTFB min/max | Schwankung (σ) | Ladezeit HTML Ø | HTML-Groesse | HTTP | Redirects |
|---|---|---|---|---|---|---|---|
| Startseite | 2528 ms | 2293 ms / 3249 ms | 364 ms | 2636 ms | 31.3 KB | 2 | 0 |
| Ausgabestellen-Uebersicht | 2633 ms | 2034 ms / 3377 ms | 530 ms | 2743 ms | 24.4 KB | 2 | 0 |
| Bewerbungsformular | 3170 ms | 2283 ms / 3571 ms | 455 ms | 3283 ms | 27.3 KB | 2 | 0 |

### Startseite
`https://www.tischlein-deckdich.at/` - Status 200, Server-IP 127.0.0.1, TLS-Handshake Ø 576 ms

Einzelmessungen TTFB: 2354 ms, 2293 ms, 2448 ms, 3249 ms, 2298 ms

**Header-Auswertung**

| Header | Wert |
|---|---|
| `server` | Apache |
| `content-type` | text/html; charset=UTF-8 |
| `cache-control` | _nicht gesetzt_ |
| `etag` | _nicht gesetzt_ |
| `last-modified` | _nicht gesetzt_ |
| `expires` | _nicht gesetzt_ |
| `content-encoding` | gzip |
| `vary` | Accept-Encoding |
| `strict-transport-security` | _nicht gesetzt_ |
| `x-content-type-options` | _nicht gesetzt_ |
| `x-frame-options` | _nicht gesetzt_ |
| `content-security-policy` | _nicht gesetzt_ |
| `referrer-policy` | _nicht gesetzt_ |
| `x-cache` | _nicht gesetzt_ |
| `cf-cache-status` | _nicht gesetzt_ |

**Kompression:** `content-encoding: gzip` - komprimiert 31.3 KB vs. unkomprimiert 170.8 KB (Einsparung 82 %)

**Uebertragene Ressourcen:** 38 Sub-Ressourcen, zusammen 722.8 KB (zzgl. 31.3 KB HTML)

| Typ | Anzahl | Summe |
|---|---|---|
| CSS | 20 | 46.3 KB |
| IMG | 6 | 601.6 KB |
| JS | 12 | 74.8 KB |

Groesste Einzelressourcen:

| Groesse | Typ | Cache-Control | Datei |
|---|---|---|---|
| 208.5 KB | image/webp | _nicht gesetzt_ | `21-Jahre-Happy-Birthday-TischleinDeckDich-1-1-1.webp` |
| 177.4 KB | image/webp | _nicht gesetzt_ | `grafik-1-1.webp` |
| 108.3 KB | image/webp | _nicht gesetzt_ | `Wir-helfen-gerne-1-1024x675.webp` |
| 42.3 KB | image/webp | _nicht gesetzt_ | `Elmar-Stuettler-1024x672.webp` |
| 32.7 KB | image/webp | _nicht gesetzt_ | `Hunger-nicht-alle-haben-genug-zu-essen-1-1-1024x683.webp` |
| 32.4 KB | image/png | _nicht gesetzt_ | `cropped-Logo.png` |
| 29.7 KB | application/javascript | _nicht gesetzt_ | `jquery.min.js?ver=3.7.1` |
| 16.9 KB | text/css | _nicht gesetzt_ | `main.min.css?ver=2.1.44` |
| 12.7 KB | text/css | _nicht gesetzt_ | `frontend_blocks.css?ver=3.20.1` |
| 9.3 KB | application/javascript | _nicht gesetzt_ | `main.js?ver=2.1.44` |

**Befunde**

- **Was gemessen/gefunden:** TTFB Ø 2528 ms
  **Risiko:** Hoch - der Server braucht vor dem ersten Byte laenger als die Zeitspanne, die Google fuer den gesamten LCP als 'gut' ansetzt.
  **Empfehlung:** Vorrangig beheben: Full-Page-Cache aktivieren, Hosting-Ressourcen und PHP-Laufzeit pruefen, ggf. CDN vorschalten.

- **Was gemessen/gefunden:** Kein `Cache-Control`-Header auf dem HTML-Dokument.
  **Risiko:** Mittel - Browser und Zwischen-Caches muessen bei jedem Aufruf neu laden; unnoetige Serverlast und laengere Wiederkehr-Ladezeiten.
  **Empfehlung:** `Cache-Control` setzen (HTML z.B. kurz, Assets `max-age=31536000, immutable`).

- **Was gemessen/gefunden:** Kompression aktiv: `gzip`
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Beibehalten; ggf. brotli ergaenzen, falls nur gzip aktiv ist.

- **Was gemessen/gefunden:** 38 von 38 Sub-Ressourcen ohne `Cache-Control`.
  **Risiko:** Mittel - Wiederkehrende Besucher laden Assets erneut.
  **Empfehlung:** Am Webserver einen Expires-/Cache-Block fuer statische Dateitypen setzen.


### Ausgabestellen-Uebersicht
`https://www.tischlein-deckdich.at/ausgabestellen/` - Status 200, Server-IP 127.0.0.1, TLS-Handshake Ø 462 ms

Einzelmessungen TTFB: 3377 ms, 2034 ms, 3136 ms, 2433 ms, 2185 ms

**Header-Auswertung**

| Header | Wert |
|---|---|
| `server` | Apache |
| `content-type` | text/html; charset=UTF-8 |
| `cache-control` | _nicht gesetzt_ |
| `etag` | _nicht gesetzt_ |
| `last-modified` | _nicht gesetzt_ |
| `expires` | _nicht gesetzt_ |
| `content-encoding` | gzip |
| `vary` | Accept-Encoding |
| `strict-transport-security` | _nicht gesetzt_ |
| `x-content-type-options` | _nicht gesetzt_ |
| `x-frame-options` | _nicht gesetzt_ |
| `content-security-policy` | _nicht gesetzt_ |
| `referrer-policy` | _nicht gesetzt_ |
| `x-cache` | _nicht gesetzt_ |
| `cf-cache-status` | _nicht gesetzt_ |

**Kompression:** `content-encoding: gzip` - komprimiert 24.4 KB vs. unkomprimiert 126.7 KB (Einsparung 81 %)

**Uebertragene Ressourcen:** 33 Sub-Ressourcen, zusammen 168.5 KB (zzgl. 24.4 KB HTML)

| Typ | Anzahl | Summe |
|---|---|---|
| CSS | 21 | 56.7 KB |
| IMG | 1 | 32.4 KB |
| JS | 11 | 79.4 KB |

Groesste Einzelressourcen:

| Groesse | Typ | Cache-Control | Datei |
|---|---|---|---|
| 32.4 KB | image/png | _nicht gesetzt_ | `cropped-Logo.png` |
| 29.7 KB | application/javascript | _nicht gesetzt_ | `jquery.min.js?ver=3.7.1` |
| 16.9 KB | text/css | _nicht gesetzt_ | `main.min.css?ver=2.1.44` |
| 12.7 KB | text/css | _nicht gesetzt_ | `frontend_blocks.css?ver=3.20.1` |
| 10.8 KB | application/javascript | _nicht gesetzt_ | `frontend_blocks_deprecated_v2.js?ver=3.20.1` |
| 10.4 KB | text/css | _nicht gesetzt_ | `frontend_blocks_deprecated_v2.css?ver=3.20.1` |
| 9.3 KB | application/javascript | _nicht gesetzt_ | `main.js?ver=2.1.44` |
| 9.0 KB | application/javascript | _nicht gesetzt_ | `scripts.js?ver=2.7.13` |
| 4.8 KB | application/javascript | _nicht gesetzt_ | `jquery-migrate.min.js?ver=3.4.1` |
| 4.2 KB | application/javascript | _nicht gesetzt_ | `index.js?ver=6.1.7` |

**Befunde**

- **Was gemessen/gefunden:** TTFB Ø 2633 ms
  **Risiko:** Hoch - der Server braucht vor dem ersten Byte laenger als die Zeitspanne, die Google fuer den gesamten LCP als 'gut' ansetzt.
  **Empfehlung:** Vorrangig beheben: Full-Page-Cache aktivieren, Hosting-Ressourcen und PHP-Laufzeit pruefen, ggf. CDN vorschalten.

- **Was gemessen/gefunden:** Kein `Cache-Control`-Header auf dem HTML-Dokument.
  **Risiko:** Mittel - Browser und Zwischen-Caches muessen bei jedem Aufruf neu laden; unnoetige Serverlast und laengere Wiederkehr-Ladezeiten.
  **Empfehlung:** `Cache-Control` setzen (HTML z.B. kurz, Assets `max-age=31536000, immutable`).

- **Was gemessen/gefunden:** Kompression aktiv: `gzip`
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Beibehalten; ggf. brotli ergaenzen, falls nur gzip aktiv ist.

- **Was gemessen/gefunden:** 33 von 33 Sub-Ressourcen ohne `Cache-Control`.
  **Risiko:** Mittel - Wiederkehrende Besucher laden Assets erneut.
  **Empfehlung:** Am Webserver einen Expires-/Cache-Block fuer statische Dateitypen setzen.


### Bewerbungsformular
`https://www.tischlein-deckdich.at/volunteer-bewerbung-bei-fahrer-in/` - Status 200, Server-IP 127.0.0.1, TLS-Handshake Ø 606 ms

Einzelmessungen TTFB: 3353 ms, 3263 ms, 2283 ms, 3381 ms, 3571 ms

**Header-Auswertung**

| Header | Wert |
|---|---|
| `server` | Apache |
| `content-type` | text/html; charset=UTF-8 |
| `cache-control` | _nicht gesetzt_ |
| `etag` | _nicht gesetzt_ |
| `last-modified` | _nicht gesetzt_ |
| `expires` | _nicht gesetzt_ |
| `content-encoding` | gzip |
| `vary` | Accept-Encoding |
| `strict-transport-security` | _nicht gesetzt_ |
| `x-content-type-options` | _nicht gesetzt_ |
| `x-frame-options` | _nicht gesetzt_ |
| `content-security-policy` | _nicht gesetzt_ |
| `referrer-policy` | _nicht gesetzt_ |
| `x-cache` | _nicht gesetzt_ |
| `cf-cache-status` | _nicht gesetzt_ |

**Kompression:** `content-encoding: gzip` - komprimiert 27.3 KB vs. unkomprimiert 135.2 KB (Einsparung 80 %)

**Uebertragene Ressourcen:** 48 Sub-Ressourcen, zusammen 319.1 KB (zzgl. 27.3 KB HTML)

| Typ | Anzahl | Summe |
|---|---|---|
| CSS | 29 | 81.5 KB |
| IMG | 1 | 32.4 KB |
| JS | 18 | 205.2 KB |

Groesste Einzelressourcen:

| Groesse | Typ | Cache-Control | Datei |
|---|---|---|---|
| 56.3 KB | application/javascript | _nicht gesetzt_ | `front.multi.min.js?ver=1.57.2` |
| 32.4 KB | image/png | _nicht gesetzt_ | `cropped-Logo.png` |
| 29.7 KB | application/javascript | _nicht gesetzt_ | `jquery.min.js?ver=3.7.1` |
| 27.8 KB | application/javascript | _nicht gesetzt_ | `inputmask.min.js?ver=1.57.2` |
| 27.1 KB | application/javascript | _nicht gesetzt_ | `jquery.inputmask.min.js?ver=1.57.2` |
| 16.9 KB | text/css | _nicht gesetzt_ | `main.min.css?ver=2.1.44` |
| 16.9 KB | text/html; charset=UTF-8 | no-cache, must-revalidate, max-age=0, no-store, private | `style-11244.css?ver=1788013605` |
| 12.7 KB | text/css | _nicht gesetzt_ | `frontend_blocks.css?ver=3.20.1` |
| 11.6 KB | application/javascript | _nicht gesetzt_ | `intlTelInput.min.js?ver=1.57.2` |
| 9.3 KB | application/javascript | _nicht gesetzt_ | `main.js?ver=2.1.44` |

**Befunde**

- **Was gemessen/gefunden:** TTFB Ø 3170 ms
  **Risiko:** Hoch - der Server braucht vor dem ersten Byte laenger als die Zeitspanne, die Google fuer den gesamten LCP als 'gut' ansetzt.
  **Empfehlung:** Vorrangig beheben: Full-Page-Cache aktivieren, Hosting-Ressourcen und PHP-Laufzeit pruefen, ggf. CDN vorschalten.

- **Was gemessen/gefunden:** Kein `Cache-Control`-Header auf dem HTML-Dokument.
  **Risiko:** Mittel - Browser und Zwischen-Caches muessen bei jedem Aufruf neu laden; unnoetige Serverlast und laengere Wiederkehr-Ladezeiten.
  **Empfehlung:** `Cache-Control` setzen (HTML z.B. kurz, Assets `max-age=31536000, immutable`).

- **Was gemessen/gefunden:** Kompression aktiv: `gzip`
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Beibehalten; ggf. brotli ergaenzen, falls nur gzip aktiv ist.

- **Was gemessen/gefunden:** 47 von 48 Sub-Ressourcen ohne `Cache-Control`.
  **Risiko:** Mittel - Wiederkehrende Besucher laden Assets erneut.
  **Empfehlung:** Am Webserver einen Expires-/Cache-Block fuer statische Dateitypen setzen.


## 2. Formulare (reine HTML-Analyse - nicht abgesendet)

### /volunteer-bewerbung-bei-fahrer-in/
`https://www.tischlein-deckdich.at/volunteer-bewerbung-bei-fahrer-in/` - HTTPS: **ja**

#### Formular 1: `ct-search-form`

- **Ziel (`action`):** `https://www.tischlein-deckdich.at/` -> https://www.tischlein-deckdich.at/
- **Methode:** GET | **enctype:** (default)
- **Felder:** 1 sichtbar, 1 versteckt, 0 als Pflichtfeld markiert

| Feldname | Typ | Pflicht | autocomplete | Platzhalter |
|---|---|---|---|---|
| `s` | search | nein | off | Start typing to search |

_Suchmaske der Website - hier werden keine personenbezogenen Daten erhoben. Die Pruefpunkte fuer Bewerbungs- und Kontaktformulare (Einwilligung, Pflichtfelder, PLZ, Uebertragungsmethode) sind nicht einschlaegig und wurden uebersprungen._

#### Formular 2: `forminator-module-11244`

- **Ziel (`action`):** `(leer)` -> https://www.tischlein-deckdich.at/volunteer-bewerbung-bei-fahrer-in/  (leeres action -> Post an dieselbe URL)
- **Methode:** POST | **enctype:** (default)
- **Felder:** 13 sichtbar, 9 versteckt, 10 als Pflichtfeld markiert

| Feldname | Typ | Pflicht | autocomplete | Platzhalter |
|---|---|---|---|---|
| `checkbox-1[]` | checkbox | nein | - | - |
| `checkbox-1[]` | checkbox | nein | - | - |
| `name-1-first-name` | text | **ja** | given-name | Niki (Bsp) |
| `name-1-last-name` | text | **ja** | family-name | Lauda (Bsp.) |
| `name-3-first-name` | text | **ja** | off | 6773 (Bsp.) |
| `name-3-last-name` | text | **ja** | off | Vandans (Bsp.) |
| `address-1-street_address` | text | **ja** | off | Römerstr. 14/2 (Bsp.) |
| `number-1` | number | **ja** | - | 1074123456 |
| `email-1` | email | **ja** | off | niki.lauda@gmail.com (Bsp.) |
| `confirm_email-1` | email | **ja** | off | Bitte noch einmal hier eingeben! |
| `phone-1` | text | **ja** | off | 06641234567 |
| `text-1` | text | nein | - | - |
| `consent-1` | checkbox | **ja** | - | - |

**Sensible Datenkategorien erkannt:**

- `(Fliesstext/Label im Formular)` -> Sozialversicherungsnummer (Art. 9 DSGVO nahe / hochsensibel, eindeutiger Personenbezug)

**Befunde**

- **Was gemessen/gefunden:** Formularseite laeuft ueber HTTPS.
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Zusaetzlich HSTS-Header setzen, falls noch nicht vorhanden.

- **Was gemessen/gefunden:** Abfrage einer Sozialversicherungsnummer im Formular ((Fliesstext/Label im Formular)).
  **Risiko:** HOCH - die SVNR ist ein eindeutiges Personenkennzeichen und fuer eine Erstbewerbung regelmaessig nicht erforderlich. Erhebung ohne Notwendigkeit verstoesst gegen die Datenminimierung (Art. 5 Abs. 1 lit. c DSGVO); in Oesterreich zusaetzlich melderechtlich sensibel.
  **Empfehlung:** Feld aus dem Bewerbungsformular entfernen und die SVNR erst bei tatsaechlichem Vertragsabschluss ueber einen gesicherten Kanal erheben.

- **Was gemessen/gefunden:** Einwilligungs-Checkbox vorhanden: `consent-1` (required)
  **Risiko:** Gering, sofern die Checkbox als Pflichtfeld gesetzt und nicht vorausgewaehlt ist.
  **Empfehlung:** Checkbox verpflichtend und unvorausgewaehlt fuehren, Einwilligungstext mit Zweckangabe und Speicherdauer versehen.

- **Was gemessen/gefunden:** Link zur Datenschutzerklaerung auf der Seite vorhanden: `https://www.tischlein-deckdich.at/datenschutzerklaerung/`
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Sicherstellen, dass der Link direkt beim Formular steht, nicht nur im Footer.

- **Was gemessen/gefunden:** Spam-/Bot-Schutz erkannt: hCaptcha
  **Risiko:** Gering fuer Spam; bei Google reCAPTCHA/hCaptcha ist der Drittland-Transfer datenschutzrechtlich zu bewerten.
  **Empfehlung:** Bei reCAPTCHA Alternative ohne US-Transfer pruefen (Friendly Captcha, ALTCHA, Honeypot) oder Transfer in der Datenschutzerklaerung ausweisen.

- **Was gemessen/gefunden:** PLZ wird laut Beschriftung abgefragt, das Eingabefeld traegt im Markup aber einen generischen Namen (kein als PLZ erkennbares Feld).
  **Risiko:** Gering - Datenqualitaet: Auswertung nach Einzugsgebiet und Validierung der Eingabe sind so nicht moeglich.
  **Empfehlung:** Eigenes PLZ-Feld mit sprechendem `name`, `inputmode="numeric"` und `pattern="[0-9]{4}"` (AT) fuehren.

- **Was gemessen/gefunden:** Telefonfeld ist nicht als `type=tel` ausgezeichnet: `phone-1` (type=text)
  **Risiko:** Gering - Bedienkomfort auf Mobilgeraeten.
  **Empfehlung:** `type="tel"` und `autocomplete="tel"` setzen.


### /volunteer-bewerbung-lagerhilfskraft-vandans/
`https://www.tischlein-deckdich.at/volunteer-bewerbung-lagerhilfskraft-vandans/` - HTTPS: **ja**

#### Formular 1: `ct-search-form`

- **Ziel (`action`):** `https://www.tischlein-deckdich.at/` -> https://www.tischlein-deckdich.at/
- **Methode:** GET | **enctype:** (default)
- **Felder:** 1 sichtbar, 1 versteckt, 0 als Pflichtfeld markiert

| Feldname | Typ | Pflicht | autocomplete | Platzhalter |
|---|---|---|---|---|
| `s` | search | nein | off | Start typing to search |

_Suchmaske der Website - hier werden keine personenbezogenen Daten erhoben. Die Pruefpunkte fuer Bewerbungs- und Kontaktformulare (Einwilligung, Pflichtfelder, PLZ, Uebertragungsmethode) sind nicht einschlaegig und wurden uebersprungen._

#### Formular 2: `forminator-module-11231`

- **Ziel (`action`):** `(leer)` -> https://www.tischlein-deckdich.at/volunteer-bewerbung-lagerhilfskraft-vandans/  (leeres action -> Post an dieselbe URL)
- **Methode:** POST | **enctype:** (default)
- **Felder:** 11 sichtbar, 9 versteckt, 10 als Pflichtfeld markiert

| Feldname | Typ | Pflicht | autocomplete | Platzhalter |
|---|---|---|---|---|
| `name-1-first-name` | text | **ja** | given-name | Niki (Bsp) |
| `name-1-last-name` | text | **ja** | family-name | Lauda (Bsp.) |
| `name-3-first-name` | text | **ja** | off | 6773 (Bsp.) |
| `name-3-last-name` | text | **ja** | off | Vandans (Bsp.) |
| `address-1-street_address` | text | **ja** | off | Römerstr. 14/2 (Bsp.) |
| `number-1` | number | **ja** | - | 1074123456 |
| `email-1` | email | **ja** | off | niki.lauda@gmail.com (Bsp.) |
| `confirm_email-1` | email | **ja** | off | Bitte noch einmal hier eingeben! |
| `phone-1` | text | **ja** | off | 06641234567 |
| `text-1` | text | nein | - | - |
| `consent-1` | checkbox | **ja** | - | - |

**Sensible Datenkategorien erkannt:**

- `(Fliesstext/Label im Formular)` -> Sozialversicherungsnummer (Art. 9 DSGVO nahe / hochsensibel, eindeutiger Personenbezug)

**Befunde**

- **Was gemessen/gefunden:** Formularseite laeuft ueber HTTPS.
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Zusaetzlich HSTS-Header setzen, falls noch nicht vorhanden.

- **Was gemessen/gefunden:** Abfrage einer Sozialversicherungsnummer im Formular ((Fliesstext/Label im Formular)).
  **Risiko:** HOCH - die SVNR ist ein eindeutiges Personenkennzeichen und fuer eine Erstbewerbung regelmaessig nicht erforderlich. Erhebung ohne Notwendigkeit verstoesst gegen die Datenminimierung (Art. 5 Abs. 1 lit. c DSGVO); in Oesterreich zusaetzlich melderechtlich sensibel.
  **Empfehlung:** Feld aus dem Bewerbungsformular entfernen und die SVNR erst bei tatsaechlichem Vertragsabschluss ueber einen gesicherten Kanal erheben.

- **Was gemessen/gefunden:** Einwilligungs-Checkbox vorhanden: `consent-1` (required)
  **Risiko:** Gering, sofern die Checkbox als Pflichtfeld gesetzt und nicht vorausgewaehlt ist.
  **Empfehlung:** Checkbox verpflichtend und unvorausgewaehlt fuehren, Einwilligungstext mit Zweckangabe und Speicherdauer versehen.

- **Was gemessen/gefunden:** Link zur Datenschutzerklaerung auf der Seite vorhanden: `https://www.tischlein-deckdich.at/datenschutzerklaerung/`
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Sicherstellen, dass der Link direkt beim Formular steht, nicht nur im Footer.

- **Was gemessen/gefunden:** Spam-/Bot-Schutz erkannt: hCaptcha
  **Risiko:** Gering fuer Spam; bei Google reCAPTCHA/hCaptcha ist der Drittland-Transfer datenschutzrechtlich zu bewerten.
  **Empfehlung:** Bei reCAPTCHA Alternative ohne US-Transfer pruefen (Friendly Captcha, ALTCHA, Honeypot) oder Transfer in der Datenschutzerklaerung ausweisen.

- **Was gemessen/gefunden:** PLZ wird laut Beschriftung abgefragt, das Eingabefeld traegt im Markup aber einen generischen Namen (kein als PLZ erkennbares Feld).
  **Risiko:** Gering - Datenqualitaet: Auswertung nach Einzugsgebiet und Validierung der Eingabe sind so nicht moeglich.
  **Empfehlung:** Eigenes PLZ-Feld mit sprechendem `name`, `inputmode="numeric"` und `pattern="[0-9]{4}"` (AT) fuehren.

- **Was gemessen/gefunden:** Telefonfeld ist nicht als `type=tel` ausgezeichnet: `phone-1` (type=text)
  **Risiko:** Gering - Bedienkomfort auf Mobilgeraeten.
  **Empfehlung:** `type="tel"` und `autocomplete="tel"` setzen.


### /volunteer-bewerbung-ausgabe-dornbirn/
`https://www.tischlein-deckdich.at/volunteer-bewerbung-ausgabe-dornbirn/` - HTTPS: **ja**

#### Formular 1: `ct-search-form`

- **Ziel (`action`):** `https://www.tischlein-deckdich.at/` -> https://www.tischlein-deckdich.at/
- **Methode:** GET | **enctype:** (default)
- **Felder:** 1 sichtbar, 1 versteckt, 0 als Pflichtfeld markiert

| Feldname | Typ | Pflicht | autocomplete | Platzhalter |
|---|---|---|---|---|
| `s` | search | nein | off | Start typing to search |

_Suchmaske der Website - hier werden keine personenbezogenen Daten erhoben. Die Pruefpunkte fuer Bewerbungs- und Kontaktformulare (Einwilligung, Pflichtfelder, PLZ, Uebertragungsmethode) sind nicht einschlaegig und wurden uebersprungen._

#### Formular 2: `forminator-module-11193`

- **Ziel (`action`):** `(leer)` -> https://www.tischlein-deckdich.at/volunteer-bewerbung-ausgabe-dornbirn/  (leeres action -> Post an dieselbe URL)
- **Methode:** POST | **enctype:** (default)
- **Felder:** 11 sichtbar, 9 versteckt, 10 als Pflichtfeld markiert

| Feldname | Typ | Pflicht | autocomplete | Platzhalter |
|---|---|---|---|---|
| `name-1-first-name` | text | **ja** | given-name | Niki (Bsp) |
| `name-1-last-name` | text | **ja** | family-name | Lauda (Bsp.) |
| `name-3-first-name` | text | **ja** | off | 6900 (Bsp.) |
| `name-3-last-name` | text | **ja** | off | Bregenz (Bsp.) |
| `address-1-street_address` | text | **ja** | off | Römerstr. 14/2 (Bsp.) |
| `number-1` | number | **ja** | - | 1074123456 |
| `email-1` | email | **ja** | off | niki.lauda@gmail.com (Bsp.) |
| `confirm_email-1` | email | **ja** | off | Bitte noch einmal hier eingeben! |
| `phone-1` | text | **ja** | off | 06641234567 |
| `text-1` | text | nein | - | - |
| `consent-1` | checkbox | **ja** | - | - |

**Sensible Datenkategorien erkannt:**

- `(Fliesstext/Label im Formular)` -> Sozialversicherungsnummer (Art. 9 DSGVO nahe / hochsensibel, eindeutiger Personenbezug)

**Befunde**

- **Was gemessen/gefunden:** Formularseite laeuft ueber HTTPS.
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Zusaetzlich HSTS-Header setzen, falls noch nicht vorhanden.

- **Was gemessen/gefunden:** Abfrage einer Sozialversicherungsnummer im Formular ((Fliesstext/Label im Formular)).
  **Risiko:** HOCH - die SVNR ist ein eindeutiges Personenkennzeichen und fuer eine Erstbewerbung regelmaessig nicht erforderlich. Erhebung ohne Notwendigkeit verstoesst gegen die Datenminimierung (Art. 5 Abs. 1 lit. c DSGVO); in Oesterreich zusaetzlich melderechtlich sensibel.
  **Empfehlung:** Feld aus dem Bewerbungsformular entfernen und die SVNR erst bei tatsaechlichem Vertragsabschluss ueber einen gesicherten Kanal erheben.

- **Was gemessen/gefunden:** Einwilligungs-Checkbox vorhanden: `consent-1` (required)
  **Risiko:** Gering, sofern die Checkbox als Pflichtfeld gesetzt und nicht vorausgewaehlt ist.
  **Empfehlung:** Checkbox verpflichtend und unvorausgewaehlt fuehren, Einwilligungstext mit Zweckangabe und Speicherdauer versehen.

- **Was gemessen/gefunden:** Link zur Datenschutzerklaerung auf der Seite vorhanden: `https://www.tischlein-deckdich.at/datenschutzerklaerung/`
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Sicherstellen, dass der Link direkt beim Formular steht, nicht nur im Footer.

- **Was gemessen/gefunden:** Spam-/Bot-Schutz erkannt: hCaptcha
  **Risiko:** Gering fuer Spam; bei Google reCAPTCHA/hCaptcha ist der Drittland-Transfer datenschutzrechtlich zu bewerten.
  **Empfehlung:** Bei reCAPTCHA Alternative ohne US-Transfer pruefen (Friendly Captcha, ALTCHA, Honeypot) oder Transfer in der Datenschutzerklaerung ausweisen.

- **Was gemessen/gefunden:** PLZ wird laut Beschriftung abgefragt, das Eingabefeld traegt im Markup aber einen generischen Namen (kein als PLZ erkennbares Feld).
  **Risiko:** Gering - Datenqualitaet: Auswertung nach Einzugsgebiet und Validierung der Eingabe sind so nicht moeglich.
  **Empfehlung:** Eigenes PLZ-Feld mit sprechendem `name`, `inputmode="numeric"` und `pattern="[0-9]{4}"` (AT) fuehren.

- **Was gemessen/gefunden:** Telefonfeld ist nicht als `type=tel` ausgezeichnet: `phone-1` (type=text)
  **Risiko:** Gering - Bedienkomfort auf Mobilgeraeten.
  **Empfehlung:** `type="tel"` und `autocomplete="tel"` setzen.


### /kontaktformular/
`https://www.tischlein-deckdich.at/kontaktformular/` - HTTPS: **ja**

#### Formular 1: `ct-search-form`

- **Ziel (`action`):** `https://www.tischlein-deckdich.at/` -> https://www.tischlein-deckdich.at/
- **Methode:** GET | **enctype:** (default)
- **Felder:** 1 sichtbar, 1 versteckt, 0 als Pflichtfeld markiert

| Feldname | Typ | Pflicht | autocomplete | Platzhalter |
|---|---|---|---|---|
| `s` | search | nein | off | Start typing to search |

_Suchmaske der Website - hier werden keine personenbezogenen Daten erhoben. Die Pruefpunkte fuer Bewerbungs- und Kontaktformulare (Einwilligung, Pflichtfelder, PLZ, Uebertragungsmethode) sind nicht einschlaegig und wurden uebersprungen._

#### Formular 2: `forminator-module-11011`

- **Ziel (`action`):** `(leer)` -> https://www.tischlein-deckdich.at/kontaktformular/  (leeres action -> Post an dieselbe URL)
- **Methode:** POST | **enctype:** (default)
- **Felder:** 6 sichtbar, 9 versteckt, 5 als Pflichtfeld markiert

| Feldname | Typ | Pflicht | autocomplete | Platzhalter |
|---|---|---|---|---|
| `name-1-first-name` | text | **ja** | given-name | - |
| `name-1-last-name` | text | **ja** | family-name | - |
| `email-1` | email | **ja** | off | - |
| `confirm_email-1` | email | **ja** | off | "Bitte noch einmal eingeben" |
| `textarea-1` | textarea | nein | - | - |
| `consent-1` | checkbox | **ja** | - | - |

**Befunde**

- **Was gemessen/gefunden:** Formularseite laeuft ueber HTTPS.
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Zusaetzlich HSTS-Header setzen, falls noch nicht vorhanden.

- **Was gemessen/gefunden:** Keine offensichtlich sensiblen Datenkategorien im Markup erkennbar.
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Beibehalten.

- **Was gemessen/gefunden:** Einwilligungs-Checkbox vorhanden: `consent-1` (required)
  **Risiko:** Gering, sofern die Checkbox als Pflichtfeld gesetzt und nicht vorausgewaehlt ist.
  **Empfehlung:** Checkbox verpflichtend und unvorausgewaehlt fuehren, Einwilligungstext mit Zweckangabe und Speicherdauer versehen.

- **Was gemessen/gefunden:** Link zur Datenschutzerklaerung auf der Seite vorhanden: `https://www.tischlein-deckdich.at/datenschutzerklaerung/`
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Sicherstellen, dass der Link direkt beim Formular steht, nicht nur im Footer.

- **Was gemessen/gefunden:** Spam-/Bot-Schutz erkannt: hCaptcha
  **Risiko:** Gering fuer Spam; bei Google reCAPTCHA/hCaptcha ist der Drittland-Transfer datenschutzrechtlich zu bewerten.
  **Empfehlung:** Bei reCAPTCHA Alternative ohne US-Transfer pruefen (Friendly Captcha, ALTCHA, Honeypot) oder Transfer in der Datenschutzerklaerung ausweisen.

- **Was gemessen/gefunden:** Kein eigenes PLZ-/Postleitzahl-Feld erkennbar.
  **Risiko:** Gering - reines Datenqualitaetsthema; Adressen landen unstrukturiert in einem Freitextfeld und sind schwerer auswertbar.
  **Empfehlung:** PLZ als eigenes Feld mit `inputmode=numeric` und `pattern=[0-9]{4}` (AT) fuehren.


## 3. SEO & Technik

- **Title:** Verteilen statt Vernichten - TISCHLEIN DECK DICH Vorarlberg (59 Zeichen)
- **Meta-Description:** Hunger: "Nicht alle haben ausreichend zu Essen!" (48 Zeichen)
- **Viewport-Meta:** width=device-width, initial-scale=1, maximum-scale=5, viewport-fit=cover
- **robots-Meta:** follow, index, max-snippet:-1, max-video-preview:-1, max-image-preview:large
- **Canonical:** https://www.tischlein-deckdich.at/
- **Generator:** WordPress 7.1
- **Sprache (`lang`):** de

**Ueberschriftenstruktur**

H1: 1 | H2: 1 | H3: 0

- `h1` Verteilen statt Vernichten!
  - `h2` TischleinDeckDich – wir retten Lebensmittel und geben sie den Armen und Bedürftigen!MITHELFEN / SPENDEN / WEITERSAGEN. DANKE!

**Bilder**

11 Bilder gesamt, davon **2 ohne `alt`-Attribut**, 0 mit leerem `alt` (dekorativ, zulaessig), 2 mit `loading="lazy"`.

| Groesse | Format | Cache-Control | Datei |
|---|---|---|---|
| 208.5 KB | image/webp | _nicht gesetzt_ | `21-Jahre-Happy-Birthday-TischleinDeckDich-1-1-1.webp` |
| 177.4 KB | image/webp | _nicht gesetzt_ | `grafik-1-1.webp` |
| 108.3 KB | image/webp | _nicht gesetzt_ | `Wir-helfen-gerne-1-1024x675.webp` |
| 42.3 KB | image/webp | _nicht gesetzt_ | `Elmar-Stuettler-1024x672.webp` |
| 32.7 KB | image/webp | _nicht gesetzt_ | `Hunger-nicht-alle-haben-genug-zu-essen-1-1-1024x683.web` |
| 32.4 KB | image/png | _nicht gesetzt_ | `cropped-Logo.png` |

**Erkannte Plugins / Frameworks**

- WordPress
- Contact Form 7 (Formular-Plugin)
- Forminator (Formular-Plugin)
- jQuery
- WP-Plugin
- WordPress-Plugins im Quelltext: `blocksy-companion`, `cf7-conditional-fields`, `cf7-views`, `contact-form-7`, `cookie-notice`, `forminator`, `hcaptcha-for-forms-and-more`, `honeypot`, `stackable-ultimate-gutenberg-blocks`

**TLS / Zertifikat**

> **Nicht auswertbar.** Die TLS-Verbindung aus dieser Ausfuehrungsumgebung wird von einem vorgeschalteten Gateway neu terminiert; sichtbar ist dessen Ersatzzertifikat, nicht das der Website. Aussteller, Laufzeit und Handshake sind daher ueber einen Netzzugang ohne Interception erneut zu pruefen (z.B. `openssl s_client` lokal oder SSL Labs).

```
issuer=O = Anthropic, CN = Egress Gateway SDS Issuing CA (production)
subject=CN = *.tischlein-deckdich.at
notBefore=Sep 10 18:00:56 2026 GMT
notAfter=Oct 10 18:01:56 2026 GMT
X509v3 Subject Alternative Name: 
    DNS:www.tischlein-deckdich.at
CONNECTION ESTABLISHED
Protocol version: TLSv1.3
Ciphersuite: TLS_AES_256_GCM_SHA384
Peer certificate: CN = *.tischlein-deckdich.at
Hash used: SHA256
Signature type: RSA-PSS
Verification: OK
Server Temp Key: X25519, 253 bits
DONE
```

**Befunde**

- **Was gemessen/gefunden:** Meta-Description vorhanden, aber mit 48 Zeichen sehr kurz: "Hunger: "Nicht alle haben ausreichend zu Essen!""
  **Risiko:** Gering - Snippet-Flaeche in der Suche wird nicht genutzt.
  **Empfehlung:** Auf 140-160 Zeichen ausbauen.

- **Was gemessen/gefunden:** Genau eine H1 vorhanden.
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Beibehalten.

- **Was gemessen/gefunden:** 2 von 11 Bildern ohne `alt`-Attribut.
  **Risiko:** Mittel - Barrierefreiheit: Screenreader koennen die Inhalte nicht wiedergeben. Fuer eine Sozialorganisation auch inhaltlich relevant; in AT greift zudem das Behindertengleichstellungsgesetz.
  **Empfehlung:** Alt-Texte ergaenzen; rein dekorative Bilder mit `alt=""` auszeichnen.

- **Was gemessen/gefunden:** 1 Bild(er) groesser als 200 KB, groesstes 208.5 KB.
  **Risiko:** Mittel - dominiert das Ladevolumen und verschlechtert LCP, besonders mobil.
  **Empfehlung:** Bilder auf Anzeigegroesse skalieren und als WebP/AVIF ausliefern; `srcset` fuer responsive Varianten nutzen.

- **Was gemessen/gefunden:** 5 Bilder werden bereits als WebP/AVIF ausgeliefert.
  **Risiko:** Gering - positiver Befund.
  **Empfehlung:** Beibehalten.

- **Was gemessen/gefunden:** Mehrere Formular-Systeme parallel eingebunden: Contact Form 7 (Formular-Plugin), Forminator (Formular-Plugin)
  **Risiko:** Mittel - doppelte Ladelast, zwei getrennte Datenspeicher fuer personenbezogene Daten und damit zwei Loeschprozesse; erhoeht Wartungs- und Datenschutzaufwand.
  **Empfehlung:** Auf ein Formularsystem konsolidieren, Altbestand samt gespeicherter Eintraege geordnet migrieren und entfernen.

- **Was gemessen/gefunden:** Kein `Strict-Transport-Security`-Header.
  **Risiko:** Gering bis mittel - erster Aufruf ueber http bleibt angreifbar (SSL-Stripping).
  **Empfehlung:** HSTS setzen, z.B. `max-age=31536000; includeSubDomains`.
