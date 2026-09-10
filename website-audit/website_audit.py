#!/usr/bin/env python3
"""
Technisches Pruefprotokoll fuer eine Website (Performance / Formular-Datenschutz / SEO+Technik).

STRIKT LESEND. Das Skript sendet ausschliesslich GET- und HEAD-Requests.
Formulare werden NUR im HTML analysiert und NIEMALS abgesendet
(kein POST, kein Ausloesen von Mails oder Datensaetzen).

Aufruf:
    python3 website_audit.py https://tischlein-deckdich.at \
        --start / \
        --ausgabestellen /ausgabestellen \
        --formular /bewerbung-fahrer \
        --formular /bewerbung-lagerhilfe \
        --formular /kontakt \
        --out bericht.md

Ohne explizite Pfade versucht das Skript, Kandidaten aus sitemap.xml und der
Startseiten-Navigation zu ermitteln und listet sie zur Auswahl auf.

Voraussetzungen: python3 (stdlib), curl, openssl.
"""

import argparse
import html
import json
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import sys
import urllib.parse
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

RUNS = 5
ASSET_WORKERS = 8
TIMEOUT = 30
UA = "Mozilla/5.0 (compatible; VereinsAudit/1.0; read-only technical audit)"

# ---------------------------------------------------------------- HTTP (nur GET/HEAD)

CURL_FMT = (
    '{"http_code":"%{http_code}","time_namelookup":%{time_namelookup},'
    '"time_connect":%{time_connect},"time_appconnect":%{time_appconnect},'
    '"time_starttransfer":%{time_starttransfer},"time_total":%{time_total},'
    '"size_download":%{size_download},"speed_download":%{speed_download},'
    '"http_version":"%{http_version}","url_effective":"%{url_effective}",'
    '"remote_ip":"%{remote_ip}","num_redirects":%{num_redirects},'
    '"size_header":%{size_header}}'
)


def _curl_once(url, method="GET", head_only=False, accept_encoding="gzip, br, deflate",
         want_headers=False, want_body=False):
    """Fuehrt genau einen GET- oder HEAD-Request aus. Andere Methoden sind gesperrt."""
    if method not in ("GET", "HEAD"):
        raise RuntimeError("Nur GET/HEAD erlaubt - dieses Skript sendet keine Formulare.")

    # Eindeutige Temp-Dateien je Aufruf: feste Namen wuerden sich bei
    # parallelen Requests gegenseitig ueberschreiben.
    tmpdir = os.environ.get("AUDIT_TMPDIR") or tempfile.gettempdir()
    hdr_fd, hdr_file = tempfile.mkstemp(prefix=".audit_hdr_", dir=tmpdir)
    os.close(hdr_fd)
    if want_body:
        body_fd, body_file = tempfile.mkstemp(prefix=".audit_body_", dir=tmpdir)
        os.close(body_fd)
    else:
        body_file = os.devnull

    cmd = ["curl", "-sS", "-L", "--max-time", str(TIMEOUT),
           "-A", UA,
           "-o", body_file,
           "-w", CURL_FMT]
    if want_body:
        # Body soll geparst werden -> curl muss die Antwort selbst auspacken.
        # (Sonst landet gzip/brotli-Rohdatenmuell im HTML-Parser.)
        cmd.append("--compressed")
    else:
        cmd += ["-H", "Accept-Encoding: " + accept_encoding]
    if head_only:
        cmd.append("-I")
    if want_headers:
        cmd += ["-D", hdr_file]
    cmd.append(url)

    def _cleanup():
        for f in (hdr_file, body_file):
            if f != os.devnull:
                try:
                    os.unlink(f)
                except OSError:
                    pass

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT + 10)
    except subprocess.TimeoutExpired:
        _cleanup()
        return {"error": "timeout"}, "", ""

    raw = proc.stdout.strip()
    m = re.search(r"\{.*\}\s*$", raw, re.S)
    if not m:
        _cleanup()
        return {"error": (proc.stderr or raw or "unbekannter curl-Fehler").strip()}, "", ""

    try:
        stats = json.loads(m.group(0))
        try:
            stats["http_code"] = int(stats.get("http_code") or 0)
        except (TypeError, ValueError):
            stats["http_code"] = 0
    except json.JSONDecodeError:
        _cleanup()
        return {"error": "curl-Ausgabe nicht lesbar: " + raw[:200]}, "", ""

    # http_code 0 heisst: gar keine HTTP-Antwort erhalten (Verbindung
    # abgebrochen). Das ist ein Transportfehler und darf nicht als
    # gueltige Messung durchgehen.
    if not stats.get("http_code"):
        _cleanup()
        return {"error": (proc.stderr or "keine HTTP-Antwort (Verbindungsabbruch)").strip()}, "", ""

    headers = ""
    if want_headers and os.path.exists(hdr_file):
        with open(hdr_file, "r", errors="replace") as fh:
            headers = fh.read()
    body = ""
    if want_body and os.path.exists(body_file):
        with open(body_file, "rb") as fh:
            body = fh.read().decode("utf-8", errors="replace")
    _cleanup()
    return stats, headers, body


RETRIES = 6


def curl(*a, **kw):
    """Retry-Wrapper: wiederholt ausschliesslich fehlgeschlagene GET/HEAD-Requests.

    Notwendig, weil der Netzwerkpfad dieser Ausfuehrungsumgebung TLS-Tunnel
    sporadisch abbricht ("Connection reset by peer"). Wiederholt wird nur bei
    Transportfehlern, niemals bei einer gueltigen HTTP-Antwort - eine 404 oder
    500 bleibt also als Messergebnis erhalten.
    """
    import time
    last = ({"error": "kein Versuch"}, "", "")
    for attempt in range(RETRIES):
        res = _curl_once(*a, **kw)
        if "error" not in res[0]:
            return res
        last = res
        time.sleep(1.5 * (attempt + 1))
    return last


def last_response_headers(raw):
    """Bei Redirects liefert curl -D mehrere Header-Bloecke - wir wollen den letzten."""
    blocks = [b for b in re.split(r"\r?\n\r?\n", raw) if b.strip().upper().startswith("HTTP/")]
    if not blocks:
        return {}
    out = OrderedDict()
    for line in blocks[-1].splitlines()[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            out.setdefault(k.strip().lower(), []).append(v.strip())
    return out


def hdr(headers, name):
    vals = headers.get(name.lower())
    return ", ".join(vals) if vals else None


# ---------------------------------------------------------------- HTML-Parser

class DocParser(HTMLParser):
    """Sammelt Formulare, Bilder, Ueberschriften, Meta-Tags, Assets."""

    FIELD_TAGS = ("input", "select", "textarea", "button")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.images = []
        self.headings = []
        self.metas = {}
        self.title = None
        self.scripts = []
        self.styles = []
        self.links = []
        self._form_stack = []
        self._heading = None
        self._buf = []
        self._in_title = False
        self._label_buf = None

    # -- helpers
    def _cur_form(self):
        return self._form_stack[-1] if self._form_stack else None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}

        if tag == "form":
            self._form_stack.append({
                "action": a.get("action", ""),
                "method": (a.get("method") or "get").lower(),
                "enctype": a.get("enctype", ""),
                "id": a.get("id", ""),
                "class": a.get("class", ""),
                "fields": [],
                "raw_text": [],
            })
        elif tag in self.FIELD_TAGS:
            f = self._cur_form()
            rec = {
                "tag": tag,
                "type": (a.get("type") or ("textarea" if tag == "textarea" else "text")).lower(),
                "name": a.get("name", ""),
                "id": a.get("id", ""),
                "required": ("required" in a) or ("aria-required" in a and a.get("aria-required") == "true"),
                "placeholder": a.get("placeholder", ""),
                "pattern": a.get("pattern", ""),
                "maxlength": a.get("maxlength", ""),
                "autocomplete": a.get("autocomplete", ""),
                "class": a.get("class", ""),
            }
            (f["fields"] if f else self.forms).append(rec) if f else None
            if f is None:
                # Feld ausserhalb eines <form> (z.B. per JS gebaut) - separat vermerken
                self.forms.append({"action": "(kein <form>-Kontext)", "method": "-",
                                   "enctype": "", "id": "", "class": "",
                                   "fields": [rec], "raw_text": [], "orphan": True})
        elif tag == "img":
            self.images.append({
                "src": a.get("src", "") or a.get("data-src", ""),
                "alt": a.get("alt"),
                "loading": a.get("loading", ""),
                "width": a.get("width", ""),
                "height": a.get("height", ""),
                "srcset": a.get("srcset", ""),
            })
        elif tag == "source":
            self.images.append({"src": a.get("srcset", "") or a.get("src", ""),
                                "alt": "(picture/source)", "loading": "", "width": "",
                                "height": "", "srcset": a.get("srcset", "")})
        elif tag in ("h1", "h2", "h3"):
            self._heading = tag
            self._buf = []
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or a.get("http-equiv") or "").lower()
            if key:
                self.metas[key] = a.get("content", "")
        elif tag == "title":
            self._in_title = True
            self._buf = []
        elif tag == "script":
            if a.get("src"):
                self.scripts.append(a["src"])
        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            href = a.get("href", "")
            if "stylesheet" in rel:
                self.styles.append(href)
            self.links.append({"rel": rel, "href": href})
        elif tag == "a":
            self.links.append({"rel": "a", "href": a.get("href", ""), "anchor": True})

    def handle_endtag(self, tag):
        if tag == "form" and self._form_stack:
            self.forms.append(self._form_stack.pop())
        elif tag in ("h1", "h2", "h3") and self._heading == tag:
            self.headings.append((tag, " ".join("".join(self._buf).split())[:140]))
            self._heading = None
            self._buf = []
        elif tag == "title":
            self.title = " ".join("".join(self._buf).split())
            self._in_title = False
            self._buf = []

    def handle_data(self, data):
        if self._heading or self._in_title:
            self._buf.append(data)
        f = self._cur_form()
        if f is not None and data.strip():
            f["raw_text"].append(data.strip())


# ---------------------------------------------------------------- Erkennungsmuster

SENSITIVE_PATTERNS = [
    (r"sozialversicher|svnr|sv-?nr|versicherungsnummer",
     "Sozialversicherungsnummer (Art. 9 DSGVO nahe / hochsensibel, eindeutiger Personenbezug)"),
    (r"geburts(datum|tag)|gebdat|birth", "Geburtsdatum"),
    (r"\biban\b|kontonummer|bankverbind", "Bankverbindung / IBAN"),
    (r"gesundheit|krank|behinder|diagnose|allergie", "Gesundheitsdaten (Art. 9 DSGVO)"),
    (r"religion|konfession", "Religionszugehoerigkeit (Art. 9 DSGVO)"),
    (r"staatsangeh|nationalit|herkunft", "Staatsangehoerigkeit / Herkunft"),
    (r"straf(register|akte)|leumund|vorstraf", "Strafrechtliche Daten (Art. 10 DSGVO)"),
    (r"ausweis|reisepass|passnummer|personalausweis", "Ausweisdaten"),
    (r"famili(en)?stand|verheirat|kinder", "Familienstand / Angehoerige"),
    (r"einkommen|gehalt|bezug|mindestsicherung|arbeitslos",
     "Einkommens-/Sozialleistungsdaten"),
    (r"f(u|ue)hrerschein|lenkerberecht", "Fuehrerscheindaten"),
]

CONSENT_PATTERNS = r"datenschutz|einwillig|zustimm|dsgvo|privacy|consent|einverstanden"
PRIVACY_LINK_PATTERNS = r"datenschutz|privacy|dsgvo"

CAPTCHA_SIGNATURES = [
    (r"hcaptcha\.com|h-captcha", "hCaptcha"),
    (r"google\.com/recaptcha|g-recaptcha|recaptcha/api", "Google reCAPTCHA"),
    (r"challenges\.cloudflare\.com|cf-turnstile", "Cloudflare Turnstile"),
    (r"friendlycaptcha|frc-captcha", "Friendly Captcha"),
    (r"altcha", "ALTCHA"),
    (r"name=[\"']?(honeypot|_gotcha|website_hp|hp_field)", "Honeypot-Feld"),
    (r"wpcf7[-_]?(quiz|recaptcha)", "CF7 Quiz/Captcha"),
]

STACK_SIGNATURES = [
    (r"/wp-content/|/wp-includes/|wp-json", "WordPress"),
    (r"wp-content/plugins/contact-form-7|wpcf7-form|id=\"wpcf7-", "Contact Form 7 (Formular-Plugin)"),
    (r"wp-content/plugins/wpforms|wpforms-form", "WPForms (Formular-Plugin)"),
    (r"wp-content/plugins/gravityforms|gform_wrapper", "Gravity Forms (Formular-Plugin)"),
    (r"wp-content/plugins/ninja-forms|nf-form-layout", "Ninja Forms (Formular-Plugin)"),
    (r"wp-content/plugins/formidable|frm_forms", "Formidable Forms (Formular-Plugin)"),
    (r"wp-content/plugins/forminator|forminator-module-|forminator-ui", "Forminator (Formular-Plugin)"),
    (r"wp-content/plugins/fluentform|fluentform-widget", "Fluent Forms (Formular-Plugin)"),
    (r"wp-content/plugins/elementor|elementor-widget-container|class=\"elementor", "Elementor (Page Builder)"),
    (r"/themes/[Dd]ivi/|class=\"et_pb_", "Divi (Theme/Builder)"),
    (r"wp-content/plugins/js_composer|js_composer_front|class=\"vc_row", "WPBakery (Page Builder)"),
    (r"bootstrap(\.min)?\.(css|js)", "Bootstrap"),
    (r"jquery(-migrate)?[.-]", "jQuery"),
    (r"google-analytics\.com|gtag/js|googletagmanager", "Google Analytics / Tag Manager (Drittland-Transfer pruefen)"),
    (r"connect\.facebook\.net|fbevents\.js", "Meta/Facebook Pixel (Drittland-Transfer pruefen)"),
    (r"fonts\.googleapis\.com|fonts\.gstatic\.com", "Google Fonts extern eingebunden (IP-Uebermittlung an Google)"),
    (r"maps\.googleapis\.com|google\.com/maps/embed", "Google Maps eingebettet"),
    (r"youtube\.com/embed|youtube-nocookie", "YouTube-Einbettung"),
    (r"borlabs|cookiebot|complianz|cookie-?consent|usercentrics|klaro", "Cookie-Consent-Tool"),
    (r"cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com|unpkg\.com", "Externes CDN"),
    (r"wp-content/plugins/([a-z0-9\-]+)", "WP-Plugin"),
]

IMAGE_EXT = re.compile(r"\.(jpe?g|png|gif|webp|avif|svg|bmp|tiff?)(\?|$)", re.I)


def detect(patterns, haystack):
    found = []
    for pat, label in patterns:
        if re.search(pat, haystack, re.I):
            found.append(label)
    return found


def wp_plugins(haystack):
    return sorted(set(re.findall(r"wp-content/plugins/([a-zA-Z0-9_\-]+)", haystack)))


# ---------------------------------------------------------------- Messungen

def measure(url, runs=RUNS):
    samples = []
    meta = {}
    failed = 0
    last_error = None
    for i in range(runs):
        stats, headers, _ = curl(url, want_headers=True)
        if "error" in stats:
            failed += 1
            last_error = stats["error"]
            continue
        samples.append(stats)
        if "headers" not in meta:
            meta["headers"] = last_response_headers(headers)
    if not samples:
        return {"url": url, "error": last_error or "kein Messlauf erfolgreich"}
    ttfb = [s["time_starttransfer"] for s in samples]
    total = [s["time_total"] for s in samples]
    connect = [s["time_appconnect"] for s in samples]
    last = samples[-1]
    return {
        "url": url,
        "final_url": last["url_effective"],
        "http_code": last["http_code"],
        "http_version": last["http_version"],
        "remote_ip": last["remote_ip"],
        "redirects": last["num_redirects"],
        "html_bytes": last["size_download"],
        "header_bytes": last["size_header"],
        "ttfb": {"avg": statistics.fmean(ttfb), "min": min(ttfb), "max": max(ttfb),
                 "stdev": statistics.pstdev(ttfb), "samples": ttfb},
        "total": {"avg": statistics.fmean(total), "min": min(total), "max": max(total)},
        "tls_handshake_avg": statistics.fmean(connect),
        "headers": meta.get("headers", {}),
        "runs_ok": len(samples),
        "runs_failed": failed,
    }


def encoding_check(url):
    """Vergleicht Antwort mit und ohne Accept-Encoding - belegt Kompression konkret."""
    with_enc, h_with, _ = curl(url, want_headers=True, accept_encoding="gzip, br, deflate")
    without, h_without, _ = curl(url, want_headers=True, accept_encoding="identity")
    hw = last_response_headers(h_with)
    ho = last_response_headers(h_without)
    return {
        "error": with_enc.get("error") or without.get("error"),
        "encoding_header": hdr(hw, "content-encoding"),
        "bytes_compressed": with_enc.get("size_download"),
        "bytes_uncompressed": without.get("size_download"),
        "vary": hdr(hw, "vary"),
        "unkomprimiert_header": hdr(ho, "content-encoding"),
    }


def asset_inventory(base_url, doc, limit=80):
    """HEAD auf alle Sub-Ressourcen - Groessen und Formate. Rein lesend."""
    urls = []
    for s in doc.scripts:
        urls.append(("JS", s))
    for s in doc.styles:
        urls.append(("CSS", s))
    for im in doc.images:
        src = (im.get("src") or "").split()[0] if im.get("src") else ""
        if src:
            urls.append(("IMG", src))

    seen, targets = set(), []
    for kind, raw in urls:
        if raw.startswith("data:"):
            continue
        absu = urllib.parse.urljoin(base_url, html.unescape(raw))
        if absu in seen:
            continue
        seen.add(absu)
        if len(targets) >= limit:
            break
        targets.append((kind, absu))

    def probe(item):
        kind, absu = item
        stats, headers, _ = curl(absu, head_only=True, want_headers=True)
        if "error" in stats:
            return {"kind": kind, "url": absu, "error": stats["error"]}
        h = last_response_headers(headers)
        size = hdr(h, "content-length")
        return {
            "kind": kind,
            "url": absu,
            "code": stats["http_code"],
            "bytes": int(size) if size and size.isdigit() else stats.get("size_download", 0),
            "ctype": hdr(h, "content-type"),
            "cache": hdr(h, "cache-control"),
            "encoding": hdr(h, "content-encoding"),
            "ttfb": stats["time_starttransfer"],
        }

    # Parallel, weil rein latenzgebunden. Es bleiben reine HEAD-Requests;
    # die gemeldeten Groessen und Header sind von der Parallelitaet unberuehrt.
    with ThreadPoolExecutor(max_workers=ASSET_WORKERS) as pool:
        return list(pool.map(probe, targets))


def tls_info(hostname):
    if not shutil.which("openssl"):
        return {"error": "openssl nicht verfuegbar"}
    try:
        p = subprocess.run(
            ["openssl", "s_client", "-connect", f"{hostname}:443",
             "-servername", hostname, "-brief"],
            input="", capture_output=True, text=True, timeout=20)
        brief = (p.stderr or "") + (p.stdout or "")
        p2 = subprocess.run(
            ["openssl", "s_client", "-connect", f"{hostname}:443",
             "-servername", hostname],
            input="", capture_output=True, text=True, timeout=20)
        cert = subprocess.run(
            ["openssl", "x509", "-noout", "-issuer", "-subject", "-dates", "-ext",
             "subjectAltName"],
            input=p2.stdout, capture_output=True, text=True, timeout=20)
        out = {"handshake": brief.strip()[:800], "cert": cert.stdout.strip()[:800]}
        if re.search(r"Egress Gateway|O = Anthropic", out["cert"], re.I):
            out["intercepted"] = True
        return out
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ---------------------------------------------------------------- Formularanalyse

def analyse_form(form, page_url, page_html):
    ctx = " ".join(form["raw_text"]) + " " + json.dumps(form["fields"], ensure_ascii=False) \
          + " " + form.get("class", "") + " " + form.get("id", "")

    fields = [f for f in form["fields"] if f["tag"] != "button"
              and f["type"] not in ("submit", "button", "image")]
    hidden = [f for f in fields if f["type"] == "hidden"]
    visible = [f for f in fields if f["type"] != "hidden"]
    required = [f for f in visible if f["required"]]

    sensitive = []
    for f in visible:
        blob = " ".join([f["name"], f["id"], f["placeholder"], f["class"]])
        for pat, label in SENSITIVE_PATTERNS:
            if re.search(pat, blob, re.I) and label not in [s[1] for s in sensitive]:
                sensitive.append((f["name"] or f["id"] or f["type"], label))
    for pat, label in SENSITIVE_PATTERNS:
        if re.search(pat, " ".join(form["raw_text"]), re.I) \
                and label not in [s[1] for s in sensitive]:
            sensitive.append(("(Fliesstext/Label im Formular)", label))

    consent = [f for f in visible if f["type"] == "checkbox"
               and re.search(CONSENT_PATTERNS,
                             " ".join([f["name"], f["id"], f["class"], f["placeholder"]]), re.I)]
    consent_text = bool(re.search(CONSENT_PATTERNS, " ".join(form["raw_text"]), re.I))

    action = form["action"].strip()
    if action in ("", "#"):
        action_abs = page_url + "  (leeres action -> Post an dieselbe URL)"
    else:
        action_abs = urllib.parse.urljoin(page_url, html.unescape(action))

    ident = " ".join([form.get("id", ""), form.get("class", "")])
    is_search = (
        bool(re.search(r"search|suche", ident, re.I))
        or (visible and all(f["type"] == "search" for f in visible))
        or ([f["name"] for f in visible] == ["s"])
    )

    return {
        "is_search": is_search,
        "plz_label": bool(re.search(r"\bplz\b|postleitzahl",
                                    " ".join(form["raw_text"]), re.I)),
        "id": form.get("id") or form.get("class") or "(ohne id)",
        "action_raw": action or "(leer)",
        "action": action_abs,
        "method": form["method"].upper(),
        "enctype": form["enctype"] or "(default)",
        "https": page_url.lower().startswith("https://"),
        "fields_visible": visible,
        "fields_hidden": hidden,
        "required": required,
        "sensitive": sensitive,
        "consent_checkboxes": consent,
        "consent_checkbox_total": [f for f in visible if f["type"] == "checkbox"],
        "consent_text_present": consent_text,
        "captcha": detect(CAPTCHA_SIGNATURES, ctx) or detect(CAPTCHA_SIGNATURES, page_html),
        "captcha_page_level": detect(CAPTCHA_SIGNATURES, page_html),
        "plz_field": [f for f in visible
                      if re.search(r"\bplz\b|postleitzahl|zip|postal", f["name"] + f["id"], re.I)],
        "email_typed": [f for f in visible if f["type"] == "email"],
        "tel_typed": [f for f in visible if f["type"] == "tel"],
        "file_uploads": [f for f in visible if f["type"] == "file"],
        "raw_text_sample": " ".join(form["raw_text"])[:400],
    }


def privacy_links(doc, page_url):
    out = []
    for l in doc.links:
        href = l.get("href", "")
        if href and re.search(PRIVACY_LINK_PATTERNS, href, re.I):
            out.append(urllib.parse.urljoin(page_url, href))
    return sorted(set(out))


# ---------------------------------------------------------------- Discovery

def discover(base):
    cands = set()
    for path in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
        stats, _, body = curl(urllib.parse.urljoin(base, path), want_body=True)
        if "error" not in stats and stats.get("http_code") == 200:
            cands.update(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body))
    stats, _, body = curl(base, want_body=True)
    if "error" not in stats:
        for href in re.findall(r'href=["\']([^"\']+)["\']', body):
            absu = urllib.parse.urljoin(base, html.unescape(href))
            if urllib.parse.urlparse(absu).netloc == urllib.parse.urlparse(base).netloc:
                cands.add(absu.split("#")[0])
    return sorted(cands)


# ---------------------------------------------------------------- Bericht

def ms(x):
    return f"{x * 1000:.0f} ms"


def kb(x):
    try:
        return f"{int(x) / 1024:.1f} KB"
    except (TypeError, ValueError):
        return "n/a"


def finding(out, was, risiko, empfehlung):
    out.append(f"- **Was gemessen/gefunden:** {was}")
    out.append(f"  **Risiko:** {risiko}")
    out.append(f"  **Empfehlung:** {empfehlung}")
    out.append("")


def build_report(base, perf_pages, form_pages, seo):
    o = []
    o.append(f"# Technisches Pruefprotokoll - {base}")
    o.append("")
    o.append(f"Methodik: {RUNS} Messungen je Seite (curl, GET), Auswertung als Mittelwert. "
             "Formulare wurden ausschliesslich im HTML-Quelltext analysiert - "
             "**es wurde kein Formular abgesendet, kein POST-Request ausgefuehrt, "
             "kein Datensatz und keine Mail ausgeloest.**")
    o.append("")
    o.append("> **Hinweis zur Abgrenzung:** Core Web Vitals (LCP, CLS, INP) sind mit curl "
             "nicht messbar - sie erfordern eine Browser-Rendering-Messung. "
             "Diese Werte sind separat ueber PageSpeed Insights / CrUX zu ergaenzen. "
             "Die hier ausgewiesene TTFB ist jedoch die serverseitige Basis, die in LCP "
             "direkt eingeht.")
    o.append("")

    if os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"):
        o.append("> **Hinweis zur Messumgebung:** Die Messungen liefen ueber einen "
                 "vorgeschalteten Proxy (Sandbox-Umgebung). Dadurch sind **nicht belastbar**: "
                 "absolute TTFB-/Ladezeitwerte (enthalten Proxy- und Relay-Laufzeit), die "
                 "ausgewiesene Server-IP (zeigt den lokalen Proxy) und die HTTP-Version "
                 "(gilt zum Proxy, nicht zum Ursprungsserver). "
                 "**Belastbar sind** alle inhaltlichen Befunde: HTML- und Formularanalyse, "
                 "Antwort-Header (Cache-Control, Kompression, Security-Header), Ressourcen"
                 "groessen sowie SEO- und Barrierefreiheitsmerkmale - diese reicht der Proxy "
                 "unveraendert durch. Ebenso belastbar sind *Vergleiche innerhalb* dieses "
                 "Berichts, da alle Seiten denselben Netzweg nutzen.")
        o.append("")

    # ---- 1 Performance
    o.append("## 1. Performance (Serverseite)")
    o.append("")
    o.append("| Seite | TTFB Ø | TTFB min/max | Schwankung (σ) | Ladezeit HTML Ø | HTML-Groesse | HTTP | Redirects |")
    o.append("|---|---|---|---|---|---|---|---|")
    for label, m in perf_pages:
        if "error" in m:
            o.append(f"| {label} | FEHLER: {m['error']} | | | | | | |")
            continue
        o.append(f"| {label} | {ms(m['ttfb']['avg'])} | {ms(m['ttfb']['min'])} / {ms(m['ttfb']['max'])} "
                 f"| {ms(m['ttfb']['stdev'])} | {ms(m['total']['avg'])} | {kb(m['html_bytes'])} "
                 f"| {m['http_version']} | {m['redirects']} |")
    o.append("")

    for label, m in perf_pages:
        if "error" in m:
            continue
        o.append(f"### {label}")
        o.append(f"`{m['final_url']}` - Status {m['http_code']}, Server-IP {m['remote_ip']}, "
                 f"TLS-Handshake Ø {ms(m['tls_handshake_avg'])}")
        o.append("")
        o.append("Einzelmessungen TTFB: " + ", ".join(ms(s) for s in m["ttfb"]["samples"])
                 + (f" - **{m['runs_failed']} von {m['runs_failed'] + m['runs_ok']} "
                    "Messlaeufen sind am Netzweg gescheitert und fehlen hier.**"
                    if m.get("runs_failed") else ""))
        o.append("")

        h = m["headers"]
        cache = hdr(h, "cache-control")
        etag = hdr(h, "etag")
        lastmod = hdr(h, "last-modified")
        expires = hdr(h, "expires")
        enc = m.get("encoding", {})

        o.append("**Header-Auswertung**")
        o.append("")
        o.append("| Header | Wert |")
        o.append("|---|---|")
        for key in ("server", "content-type", "cache-control", "etag", "last-modified",
                    "expires", "content-encoding", "vary", "strict-transport-security",
                    "x-content-type-options", "x-frame-options", "content-security-policy",
                    "referrer-policy", "x-cache", "cf-cache-status"):
            o.append(f"| `{key}` | {hdr(h, key) or '_nicht gesetzt_'} |")
        o.append("")

        if enc:
            saved = ""
            if enc.get("bytes_uncompressed") and enc.get("bytes_compressed"):
                try:
                    ratio = 100 * (1 - enc["bytes_compressed"] / enc["bytes_uncompressed"])
                    saved = f" (Einsparung {ratio:.0f} %)"
                except ZeroDivisionError:
                    pass
            shown = enc.get("encoding_header") or hdr(h, "content-encoding") \
                or ("nicht ermittelbar" if enc.get("error") else "KEINE")
            o.append(f"**Kompression:** `content-encoding: {shown}` - "
                     f"komprimiert {kb(enc.get('bytes_compressed'))} vs. unkomprimiert "
                     f"{kb(enc.get('bytes_uncompressed'))}{saved}")
            o.append("")

        assets = m.get("assets") or []
        if assets:
            total = sum(a.get("bytes", 0) or 0 for a in assets)
            by_kind = {}
            for a in assets:
                by_kind.setdefault(a["kind"], [0, 0])
                by_kind[a["kind"]][0] += 1
                by_kind[a["kind"]][1] += a.get("bytes", 0) or 0
            o.append(f"**Uebertragene Ressourcen:** {len(assets)} Sub-Ressourcen, "
                     f"zusammen {kb(total)} (zzgl. {kb(m['html_bytes'])} HTML)")
            o.append("")
            o.append("| Typ | Anzahl | Summe |")
            o.append("|---|---|---|")
            for k, (n, b) in sorted(by_kind.items()):
                o.append(f"| {k} | {n} | {kb(b)} |")
            o.append("")
            big = sorted([a for a in assets if a.get("bytes")],
                         key=lambda a: -a["bytes"])[:10]
            if big:
                o.append("Groesste Einzelressourcen:")
                o.append("")
                o.append("| Groesse | Typ | Cache-Control | Datei |")
                o.append("|---|---|---|---|")
                for a in big:
                    o.append(f"| {kb(a['bytes'])} | {a.get('ctype') or a['kind']} | "
                             f"{a.get('cache') or '_nicht gesetzt_'} | `{a['url'].split('/')[-1][:60]}` |")
                o.append("")

        o.append("**Befunde**")
        o.append("")
        avg = m["ttfb"]["avg"]
        if avg < 0.2:
            finding(o, f"TTFB Ø {ms(avg)}", "Gering - Wert liegt im gruenen Bereich (< 200 ms).",
                    "Beibehalten, keine Massnahme noetig.")
        elif avg < 0.6:
            finding(o, f"TTFB Ø {ms(avg)}",
                    "Mittel - spuerbare Serverlatenz, geht 1:1 in den LCP ein.",
                    "Serverseitiges Full-Page-Caching bzw. Objekt-Cache pruefen; PHP-Version und "
                    "Datenbankabfragen der Seite untersuchen.")
        else:
            finding(o, f"TTFB Ø {ms(avg)}",
                    "Hoch - der Server braucht vor dem ersten Byte laenger als die Zeitspanne, "
                    "die Google fuer den gesamten LCP als 'gut' ansetzt.",
                    "Vorrangig beheben: Full-Page-Cache aktivieren, Hosting-Ressourcen und "
                    "PHP-Laufzeit pruefen, ggf. CDN vorschalten.")

        if not cache:
            finding(o, "Kein `Cache-Control`-Header auf dem HTML-Dokument.",
                    "Mittel - Browser und Zwischen-Caches muessen bei jedem Aufruf neu laden; "
                    "unnoetige Serverlast und laengere Wiederkehr-Ladezeiten.",
                    "`Cache-Control` setzen (HTML z.B. kurz, Assets `max-age=31536000, immutable`).")
        else:
            finding(o, f"`Cache-Control: {cache}`" + (f", ETag vorhanden ({etag})" if etag else ", kein ETag"),
                    "Gering bis mittel - abhaengig davon, ob die Direktive zur Aktualisierungs"
                    "frequenz der Inhalte passt.",
                    "Statische Assets langfristig cachen, HTML kurz - Validierung ueber ETag/"
                    "Last-Modified sicherstellen." + ("" if etag or lastmod else " ETag und Last-Modified fehlen beide."))

        enc_header = enc.get("encoding_header") or hdr(h, "content-encoding")
        if enc_header:
            finding(o, f"Kompression aktiv: `{enc_header}`",
                    "Gering - positiver Befund.",
                    "Beibehalten; ggf. brotli ergaenzen, falls nur gzip aktiv ist.")
        elif enc.get("error"):
            finding(o, "Kompression nicht ermittelbar - der Vergleichsrequest ist "
                    f"fehlgeschlagen ({enc['error'][:120]}).",
                    "Offen - kein Befund, nur eine Messluecke.",
                    "Pruefung wiederholen, bevor daraus eine Massnahme abgeleitet wird.")
        else:
            finding(o, "Kein `Content-Encoding` in der Antwort - HTML wird unkomprimiert ausgeliefert.",
                    "Mittel - deutlich mehr uebertragene Bytes, spuerbar bei Mobilfunk.",
                    "gzip (mind.) bzw. brotli am Webserver aktivieren.")

        uncached = [a for a in assets if not a.get("cache")]
        if uncached:
            finding(o, f"{len(uncached)} von {len(assets)} Sub-Ressourcen ohne `Cache-Control`.",
                    "Mittel - Wiederkehrende Besucher laden Assets erneut.",
                    "Am Webserver einen Expires-/Cache-Block fuer statische Dateitypen setzen.")
        o.append("")

    # ---- 2 Formulare
    o.append("## 2. Formulare (reine HTML-Analyse - nicht abgesendet)")
    o.append("")
    for label, page in form_pages:
        o.append(f"### {label}")
        if page.get("error"):
            o.append(f"FEHLER beim Abruf: {page['error']}")
            o.append("")
            continue
        o.append(f"`{page['url']}` - HTTPS: **{'ja' if page['https'] else 'NEIN'}**")
        o.append("")
        if not page["forms"]:
            o.append("_Kein `<form>`-Element im ausgelieferten HTML gefunden "
                     "(moeglicherweise per JavaScript nachgeladen oder als iframe eingebettet)._")
            iframes = page.get("iframes") or []
            if iframes:
                o.append("")
                o.append("Eingebettete iframes: " + ", ".join(f"`{i}`" for i in iframes))
            o.append("")
            continue

        for idx, f in enumerate(page["forms"], 1):
            o.append(f"#### Formular {idx}: `{f['id']}`")
            o.append("")
            o.append(f"- **Ziel (`action`):** `{f['action_raw']}` -> {f['action']}")
            o.append(f"- **Methode:** {f['method']} | **enctype:** {f['enctype']}")
            o.append(f"- **Felder:** {len(f['fields_visible'])} sichtbar, "
                     f"{len(f['fields_hidden'])} versteckt, "
                     f"{len(f['required'])} als Pflichtfeld markiert")
            o.append("")
            o.append("| Feldname | Typ | Pflicht | autocomplete | Platzhalter |")
            o.append("|---|---|---|---|---|")
            for fld in f["fields_visible"]:
                o.append(f"| `{fld['name'] or fld['id'] or '(ohne name)'}` | {fld['type']} | "
                         f"{'**ja**' if fld['required'] else 'nein'} | "
                         f"{fld['autocomplete'] or '-'} | {fld['placeholder'][:40] or '-'} |")
            o.append("")

            if f.get("is_search"):
                o.append("_Suchmaske der Website - hier werden keine personenbezogenen "
                         "Daten erhoben. Die Pruefpunkte fuer Bewerbungs- und "
                         "Kontaktformulare (Einwilligung, Pflichtfelder, PLZ, "
                         "Uebertragungsmethode) sind nicht einschlaegig und wurden "
                         "uebersprungen._")
                o.append("")
                continue

            if f["sensitive"]:
                o.append("**Sensible Datenkategorien erkannt:**")
                o.append("")
                for name, label in f["sensitive"]:
                    o.append(f"- `{name}` -> {label}")
                o.append("")

            o.append("**Befunde**")
            o.append("")

            if not f["https"]:
                finding(o, "Formularseite wird nicht ueber HTTPS ausgeliefert.",
                        "HOCH - Eingaben waeren im Klartext uebertragbar; bei Bewerbungsdaten ein "
                        "Verstoss gegen Art. 32 DSGVO (Sicherheit der Verarbeitung).",
                        "HTTPS erzwingen (Redirect + HSTS).")
            else:
                finding(o, "Formularseite laeuft ueber HTTPS.", "Gering - positiver Befund.",
                        "Zusaetzlich HSTS-Header setzen, falls noch nicht vorhanden.")

            svnr = [s for s in f["sensitive"] if "Sozialversicherung" in s[1]]
            if svnr:
                finding(o, f"Abfrage einer Sozialversicherungsnummer im Formular ({svnr[0][0]}).",
                        "HOCH - die SVNR ist ein eindeutiges Personenkennzeichen und fuer eine "
                        "Erstbewerbung regelmaessig nicht erforderlich. Erhebung ohne Notwendigkeit "
                        "verstoesst gegen die Datenminimierung (Art. 5 Abs. 1 lit. c DSGVO); "
                        "in Oesterreich zusaetzlich melderechtlich sensibel.",
                        "Feld aus dem Bewerbungsformular entfernen und die SVNR erst bei "
                        "tatsaechlichem Vertragsabschluss ueber einen gesicherten Kanal erheben.")
            elif f["sensitive"]:
                finding(o, "Sensible bzw. besonders schuetzenswerte Felder im Formular: "
                        + "; ".join(f"{n} ({l})" for n, l in f["sensitive"]),
                        "Mittel bis hoch - je Kategorie ist die Erforderlichkeit im Bewerbungs"
                        "stadium zu pruefen (Art. 5 Abs. 1 lit. c, ggf. Art. 9 DSGVO).",
                        "Nicht zwingend benoetigte Felder streichen oder optional stellen; "
                        "Erforderlichkeit je Feld dokumentieren.")
            else:
                finding(o, "Keine offensichtlich sensiblen Datenkategorien im Markup erkennbar.",
                        "Gering - positiver Befund.",
                        "Beibehalten.")

            if f["consent_checkboxes"]:
                finding(o, f"Einwilligungs-Checkbox vorhanden: "
                        + ", ".join(f"`{c['name'] or c['id']}`"
                                    + (" (required)" if c["required"] else " (**nicht** required)")
                                    for c in f["consent_checkboxes"]),
                        "Gering, sofern die Checkbox als Pflichtfeld gesetzt und nicht "
                        "vorausgewaehlt ist." if all(c["required"] for c in f["consent_checkboxes"])
                        else "Mittel - Checkbox vorhanden, aber nicht als Pflichtfeld markiert; "
                             "die Einwilligung kann uebersprungen werden.",
                        "Checkbox verpflichtend und unvorausgewaehlt fuehren, Einwilligungstext "
                        "mit Zweckangabe und Speicherdauer versehen.")
            elif f["consent_text_present"]:
                finding(o, "Datenschutzhinweis als Fliesstext im Formular, aber keine "
                        "eigene Einwilligungs-Checkbox im Markup.",
                        "Mittel - eine Einwilligung muss aktiv und nachweisbar erteilt werden "
                        "(Art. 7 Abs. 1 DSGVO). Blosser Hinweistext ist kein Nachweis.",
                        "Explizite, unvorausgewaehlte Pflicht-Checkbox ergaenzen und die "
                        "Zustimmung samt Zeitstempel protokollieren.")
            else:
                finding(o, "Weder Einwilligungs-Checkbox noch Datenschutzhinweis im Formular-Markup.",
                        "HOCH - fuer die Verarbeitung von Bewerbungsdaten fehlt der Nachweis "
                        "der Information und ggf. der Einwilligung (Art. 7, 13 DSGVO).",
                        "Pflicht-Checkbox mit Verlinkung auf die Datenschutzerklaerung ergaenzen.")

            if page["privacy_links"]:
                finding(o, "Link zur Datenschutzerklaerung auf der Seite vorhanden: "
                        + ", ".join(f"`{p}`" for p in page["privacy_links"][:3]),
                        "Gering - positiver Befund.",
                        "Sicherstellen, dass der Link direkt beim Formular steht, nicht nur im Footer.")
            else:
                finding(o, "Kein Link zur Datenschutzerklaerung auf der Formularseite gefunden.",
                        "HOCH - Informationspflicht nach Art. 13 DSGVO nicht erfuellt.",
                        "Datenschutzerklaerung verlinken, direkt beim Absende-Button.")

            if f["captcha"]:
                finding(o, "Spam-/Bot-Schutz erkannt: " + ", ".join(sorted(set(f["captcha"]))),
                        "Gering fuer Spam; bei Google reCAPTCHA/hCaptcha ist der Drittland-"
                        "Transfer datenschutzrechtlich zu bewerten.",
                        "Bei reCAPTCHA Alternative ohne US-Transfer pruefen (Friendly Captcha, "
                        "ALTCHA, Honeypot) oder Transfer in der Datenschutzerklaerung ausweisen.")
            else:
                finding(o, "Kein Spam-/Bot-Schutz im Markup erkennbar (weder Captcha noch Honeypot).",
                        "Mittel - offenes Formular ist anfaellig fuer automatisierte Spam-Eintraege; "
                        "bei Mailversand droht Missbrauch als Spam-Relay.",
                        "Serverseitige Rate-Limitierung plus datenschutzfreundliches Captcha "
                        "oder Honeypot-Feld ergaenzen.")

            if f["method"] == "GET":
                finding(o, "Formular verwendet `method=GET`.",
                        "HOCH bei personenbezogenen Daten - Eingaben landen in der URL, damit in "
                        "Server-Logs, Browserverlauf und Referrer-Headern.",
                        "Auf `method=POST` umstellen.")

            if f["file_uploads"]:
                finding(o, f"{len(f['file_uploads'])} Datei-Upload-Feld(er) "
                        + ", ".join(f"`{u['name']}`" for u in f["file_uploads"]),
                        "Mittel - Uploads koennen Lebenslaeufe mit sensiblen Daten enthalten; "
                        "Ablageort und Zugriffsschutz sind zu pruefen.",
                        "Dateitypen und -groesse serverseitig begrenzen, Ablage ausserhalb des "
                        "Webroots, Loeschfristen definieren.")

            if not f["plz_field"] and f.get("plz_label"):
                finding(o, "PLZ wird laut Beschriftung abgefragt, das Eingabefeld traegt "
                        "im Markup aber einen generischen Namen (kein als PLZ erkennbares Feld).",
                        "Gering - Datenqualitaet: Auswertung nach Einzugsgebiet und "
                        "Validierung der Eingabe sind so nicht moeglich.",
                        "Eigenes PLZ-Feld mit sprechendem `name`, `inputmode=\"numeric\"` "
                        "und `pattern=\"[0-9]{4}\"` (AT) fuehren.")
            elif not f["plz_field"]:
                finding(o, "Kein eigenes PLZ-/Postleitzahl-Feld erkennbar.",
                        "Gering - reines Datenqualitaetsthema; Adressen landen unstrukturiert "
                        "in einem Freitextfeld und sind schwerer auswertbar.",
                        "PLZ als eigenes Feld mit `inputmode=numeric` und `pattern=[0-9]{4}` "
                        "(AT) fuehren.")
            else:
                pf = f["plz_field"][0]
                if pf["type"] not in ("text", "number", "tel") or not pf["pattern"]:
                    finding(o, f"PLZ-Feld `{pf['name']}` vorhanden (type={pf['type']}, "
                            f"pattern={pf['pattern'] or 'keins'}).",
                            "Gering - ohne Validierungsmuster sind Fehleingaben wahrscheinlich.",
                            "`pattern=\"[0-9]{4}\"` und `inputmode=\"numeric\"` ergaenzen.")
                else:
                    finding(o, f"PLZ als eigenes, validiertes Feld (`{pf['name']}`).",
                            "Gering - positiver Befund.", "Beibehalten.")

            mail_like = [x for x in f["fields_visible"]
                         if re.search(r"mail", x["name"] + x["id"], re.I)]
            if mail_like and not f["email_typed"]:
                finding(o, "E-Mail-Feld ist nicht als `type=email` ausgezeichnet: "
                        + ", ".join(f"`{x['name']}` (type={x['type']})" for x in mail_like),
                        "Gering - keine Browser-Validierung, auf Mobilgeraeten falsche Tastatur.",
                        "`type=\"email\"` und `autocomplete=\"email\"` setzen.")
            tel_like = [x for x in f["fields_visible"]
                        if re.search(r"tel|phone|handy|mobil", x["name"] + x["id"], re.I)]
            if tel_like and not f["tel_typed"]:
                finding(o, "Telefonfeld ist nicht als `type=tel` ausgezeichnet: "
                        + ", ".join(f"`{x['name']}` (type={x['type']})" for x in tel_like),
                        "Gering - Bedienkomfort auf Mobilgeraeten.",
                        "`type=\"tel\"` und `autocomplete=\"tel\"` setzen.")

            if not f["required"]:
                finding(o, "Kein einziges Feld ist mit `required` ausgezeichnet.",
                        "Gering bis mittel - Validierung erfolgt allenfalls serverseitig oder "
                        "gar nicht; unvollstaendige Bewerbungen erzeugen Nacharbeit.",
                        "Pflichtfelder im Markup kennzeichnen (`required` + visuelle Markierung) "
                        "und serverseitig gegenpruefen.")
            o.append("")

    # ---- 3 SEO & Technik
    o.append("## 3. SEO & Technik")
    o.append("")
    if seo.get("error"):
        o.append(f"FEHLER: {seo['error']}")
        return "\n".join(o)

    desc = seo.get("description")
    o.append(f"- **Title:** {seo.get('title') or '_fehlt_'} "
             f"({len(seo.get('title') or '')} Zeichen)")
    o.append(f"- **Meta-Description:** {desc or '_fehlt_'} "
             f"({len(desc or '')} Zeichen)")
    o.append(f"- **Viewport-Meta:** {seo.get('viewport') or '_fehlt_'}")
    o.append(f"- **robots-Meta:** {seo.get('robots') or '_nicht gesetzt_'}")
    o.append(f"- **Canonical:** {seo.get('canonical') or '_nicht gesetzt_'}")
    o.append(f"- **Generator:** {seo.get('generator') or '_nicht gesetzt_'}")
    o.append(f"- **Sprache (`lang`):** {seo.get('lang') or '_nicht gesetzt_'}")
    o.append("")

    o.append("**Ueberschriftenstruktur**")
    o.append("")
    o.append(f"H1: {seo['h1_count']} | H2: {seo['h2_count']} | H3: {seo['h3_count']}")
    o.append("")
    for tag, text in seo["headings"][:25]:
        o.append(f"{'  ' * (int(tag[1]) - 1)}- `{tag}` {text}")
    o.append("")

    o.append("**Bilder**")
    o.append("")
    o.append(f"{seo['img_total']} Bilder gesamt, davon **{seo['img_no_alt']} ohne `alt`-Attribut**, "
             f"{seo['img_empty_alt']} mit leerem `alt` (dekorativ, zulaessig), "
             f"{seo['img_lazy']} mit `loading=\"lazy\"`.")
    o.append("")
    if seo["image_assets"]:
        o.append("| Groesse | Format | Cache-Control | Datei |")
        o.append("|---|---|---|---|")
        for a in seo["image_assets"][:15]:
            o.append(f"| {kb(a.get('bytes'))} | {a.get('ctype') or '?'} | "
                     f"{a.get('cache') or '_nicht gesetzt_'} | `{a['url'].split('/')[-1][:55]}` |")
        o.append("")

    o.append("**Erkannte Plugins / Frameworks**")
    o.append("")
    for s in seo["stack"]:
        o.append(f"- {s}")
    if seo["wp_plugins"]:
        o.append(f"- WordPress-Plugins im Quelltext: " + ", ".join(f"`{p}`" for p in seo["wp_plugins"]))
    o.append("")

    o.append("**TLS / Zertifikat**")
    o.append("")
    if seo["tls"].get("intercepted"):
        o.append("> **Nicht auswertbar.** Die TLS-Verbindung aus dieser Ausfuehrungsumgebung wird "
                 "von einem vorgeschalteten Gateway neu terminiert; sichtbar ist dessen "
                 "Ersatzzertifikat, nicht das der Website. Aussteller, Laufzeit und Handshake "
                 "sind daher ueber einen Netzzugang ohne Interception erneut zu pruefen "
                 "(z.B. `openssl s_client` lokal oder SSL Labs).")
        o.append("")
    o.append("```")
    o.append(seo["tls"].get("cert") or seo["tls"].get("error", "n/a"))
    o.append(seo["tls"].get("handshake", ""))
    o.append("```")
    o.append("")

    o.append("**Befunde**")
    o.append("")
    if not desc:
        finding(o, "Startseite hat keine Meta-Description.",
                "Mittel - Google generiert das Snippet selbst; die Wirkung in den Suchergebnissen "
                "ist nicht steuerbar, was fuer einen Verein mit Spenden-/Freiwilligenakquise relevant ist.",
                "Meta-Description mit 140-160 Zeichen ergaenzen, inkl. Ort und Zweck des Vereins.")
    elif len(desc) < 70:
        finding(o, f"Meta-Description vorhanden, aber mit {len(desc)} Zeichen sehr kurz: \"{desc}\"",
                "Gering - Snippet-Flaeche in der Suche wird nicht genutzt.",
                "Auf 140-160 Zeichen ausbauen.")
    elif len(desc) > 165:
        finding(o, f"Meta-Description mit {len(desc)} Zeichen zu lang - wird abgeschnitten.",
                "Gering.", "Auf 140-160 Zeichen kuerzen.")
    else:
        finding(o, f"Meta-Description vorhanden und mit {len(desc)} Zeichen gut dimensioniert.",
                "Gering - positiver Befund.", "Beibehalten.")

    if seo["h1_count"] == 0:
        finding(o, "Keine H1-Ueberschrift auf der Startseite.",
                "Mittel - fehlende Dokumenthierarchie beeintraechtigt Screenreader-Navigation "
                "und die semantische Einordnung durch Suchmaschinen.",
                "Genau eine H1 setzen, die den Vereinszweck benennt.")
    elif seo["h1_count"] > 1:
        finding(o, f"{seo['h1_count']} H1-Ueberschriften auf der Startseite.",
                "Gering - uneindeutige Hierarchie; haeufige Nebenwirkung von Page Buildern.",
                "Auf eine H1 reduzieren, weitere als H2 auszeichnen.")
    else:
        finding(o, "Genau eine H1 vorhanden.", "Gering - positiver Befund.", "Beibehalten.")

    if seo["img_no_alt"]:
        finding(o, f"{seo['img_no_alt']} von {seo['img_total']} Bildern ohne `alt`-Attribut.",
                "Mittel - Barrierefreiheit: Screenreader koennen die Inhalte nicht wiedergeben. "
                "Fuer eine Sozialorganisation auch inhaltlich relevant; in AT greift zudem das "
                "Behindertengleichstellungsgesetz.",
                "Alt-Texte ergaenzen; rein dekorative Bilder mit `alt=\"\"` auszeichnen.")
    else:
        finding(o, "Alle Bilder haben ein `alt`-Attribut.", "Gering - positiver Befund.",
                "Beibehalten.")

    legacy = [a for a in seo["image_assets"]
              if a.get("ctype") and re.search(r"jpeg|jpg|png", a["ctype"], re.I)]
    heavy = [a for a in seo["image_assets"] if (a.get("bytes") or 0) > 200 * 1024]
    modern = [a for a in seo["image_assets"]
              if a.get("ctype") and re.search(r"webp|avif", a["ctype"], re.I)]
    if heavy:
        finding(o, f"{len(heavy)} Bild(er) groesser als 200 KB, groesstes "
                f"{kb(max(a['bytes'] for a in heavy))}.",
                "Mittel - dominiert das Ladevolumen und verschlechtert LCP, besonders mobil.",
                "Bilder auf Anzeigegroesse skalieren und als WebP/AVIF ausliefern; "
                "`srcset` fuer responsive Varianten nutzen.")
    if legacy and not modern:
        finding(o, f"{len(legacy)} Bilder ausschliesslich als JPEG/PNG, kein WebP/AVIF im Einsatz.",
                "Gering bis mittel - typisch 25-35 % vermeidbares Ladevolumen.",
                "Konvertierungs-Plugin oder Build-Schritt fuer WebP einrichten.")
    elif modern:
        finding(o, f"{len(modern)} Bilder werden bereits als WebP/AVIF ausgeliefert.",
                "Gering - positiver Befund.", "Beibehalten.")

    form_plugins = [s for s in seo["stack"] if "Formular-Plugin" in s]
    if len(form_plugins) > 1:
        finding(o, "Mehrere Formular-Systeme parallel eingebunden: " + ", ".join(form_plugins),
                "Mittel - doppelte Ladelast, zwei getrennte Datenspeicher fuer personenbezogene "
                "Daten und damit zwei Loeschprozesse; erhoeht Wartungs- und Datenschutzaufwand.",
                "Auf ein Formularsystem konsolidieren, Altbestand samt gespeicherter Eintraege "
                "geordnet migrieren und entfernen.")
    elif form_plugins:
        finding(o, "Ein einheitliches Formularsystem im Einsatz: " + form_plugins[0],
                "Gering - positiver Befund.", "Beibehalten.")

    third = [s for s in seo["stack"] if "Drittland" in s or "Google Fonts" in s]
    if third:
        finding(o, "Externe Dienste eingebunden: " + ", ".join(third),
                "Mittel bis hoch - IP-Adressen der Besucher werden an Dritte uebermittelt. "
                "Ohne vorherige Einwilligung in AT/EU angreifbar (vgl. Google-Fonts-Entscheidungen).",
                "Google Fonts lokal hosten; Analyse-/Tracking-Dienste erst nach Consent laden "
                "und in der Datenschutzerklaerung ausweisen.")
    if not any("Cookie-Consent" in s for s in seo["stack"]) and third:
        finding(o, "Kein Cookie-/Consent-Tool erkannt, obwohl externe Dienste eingebunden sind.",
                "HOCH - einwilligungspflichtige Dienste laden ohne Einwilligung (§ 165 TKG 2021, "
                "Art. 6 DSGVO).",
                "Consent-Management einrichten, das die Dienste erst nach Zustimmung nachlaedt.")

    hsts = hdr(seo.get("headers", {}), "strict-transport-security")
    if not hsts:
        finding(o, "Kein `Strict-Transport-Security`-Header.",
                "Gering bis mittel - erster Aufruf ueber http bleibt angreifbar (SSL-Stripping).",
                "HSTS setzen, z.B. `max-age=31536000; includeSubDomains`.")
    else:
        finding(o, f"HSTS aktiv: `{hsts}`", "Gering - positiver Befund.", "Beibehalten.")

    return "\n".join(o)


# ---------------------------------------------------------------- Ablauf

def load_page(url):
    stats, headers, body = curl(url, want_headers=True, want_body=True)
    if "error" in stats:
        return {"url": url, "error": stats["error"]}
    doc = DocParser()
    try:
        doc.feed(body)
    except Exception:  # noqa: BLE001
        pass
    final = stats.get("url_effective", url)
    analysed = [analyse_form(f, final, body) for f in doc.forms if f.get("fields")]
    # Nur Formulare mit mindestens einem auswertbaren Eingabefeld behalten.
    # Einzelne Buttons ausserhalb eines <form> (Menue-Toggles, Suche-Icons)
    # landen sonst als Pseudo-Formular mit null Feldern im Bericht und
    # erzeugen dort Fehlbefunde ("keine Einwilligung", "kein Spam-Schutz").
    forms = [f for f in analysed if f["fields_visible"]]
    return {
        "url": final,
        "https": final.lower().startswith("https://"),
        "doc": doc,
        "html": body,
        "headers": last_response_headers(headers),
        "forms": forms,
        "privacy_links": privacy_links(doc, final),
        "iframes": re.findall(r'<iframe[^>]+src=["\']([^"\']+)', body, re.I),
        "stats": stats,
    }


def main():
    global RUNS
    ap = argparse.ArgumentParser(description="Read-only Website-Audit (sendet keine Formulare).")
    ap.add_argument("base", help="Basis-URL, z.B. https://tischlein-deckdich.at")
    ap.add_argument("--start", default="/")
    ap.add_argument("--ausgabestellen", default=None)
    ap.add_argument("--formular", action="append", default=[],
                    help="Pfad einer Formularseite (mehrfach angebbar)")
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--out", default="pruefprotokoll.md")
    ap.add_argument("--discover", action="store_true",
                    help="Nur URLs auflisten (sitemap.xml + Navigation), nichts messen")
    args = ap.parse_args()

    RUNS = args.runs
    base = args.base.rstrip("/")

    if args.discover or not (args.ausgabestellen and args.formular):
        print("URL-Discovery laeuft ...", file=sys.stderr)
        for u in discover(base + "/"):
            print(u)
        if args.discover:
            return
        if not (args.ausgabestellen and args.formular):
            print("\nBitte --ausgabestellen und mindestens ein --formular aus der Liste oben "
                  "angeben und erneut starten.", file=sys.stderr)
            return

    perf_targets = [("Startseite", urllib.parse.urljoin(base + "/", args.start)),
                    ("Ausgabestellen-Uebersicht",
                     urllib.parse.urljoin(base + "/", args.ausgabestellen)),
                    ("Bewerbungsformular", urllib.parse.urljoin(base + "/", args.formular[0]))]

    perf_pages = []
    for label, url in perf_targets:
        print(f"[perf] {label}: {RUNS} Messungen ...", file=sys.stderr)
        m = measure(url, RUNS)
        if "error" not in m:
            m["encoding"] = encoding_check(url)
            page = load_page(url)
            if not page.get("error"):
                print(f"[perf] {label}: Ressourcen-Inventur ...", file=sys.stderr)
                m["assets"] = asset_inventory(m["final_url"], page["doc"])
        perf_pages.append((label, m))

    form_pages = []
    for path in args.formular:
        url = urllib.parse.urljoin(base + "/", path)
        print(f"[form] Analysiere HTML von {url} (kein Absenden) ...", file=sys.stderr)
        form_pages.append((path, load_page(url)))

    print("[seo] Startseite auswerten ...", file=sys.stderr)
    home = load_page(urllib.parse.urljoin(base + "/", args.start))
    if home.get("error"):
        seo = {"error": home["error"]}
    else:
        doc = home["doc"]
        imgs = doc.images
        # Stack ueber Startseite UND die geprueften Formularseiten ermitteln:
        # Formular-Plugins laden ihre Assets nur dort, wo ein Formular steht.
        stack_html = home["html"] + "".join(
            pg["html"] for _, pg in form_pages if not pg.get("error"))
        stack = detect(STACK_SIGNATURES, stack_html)
        img_assets = [a for a in (perf_pages[0][1].get("assets") or [])
                      if a["kind"] == "IMG" or (a.get("ctype") or "").startswith("image/")]
        lang = re.search(r"<html[^>]+lang=[\"']([^\"']+)", home["html"], re.I)
        seo = {
            "title": doc.title,
            "description": doc.metas.get("description"),
            "viewport": doc.metas.get("viewport"),
            "robots": doc.metas.get("robots"),
            "generator": doc.metas.get("generator"),
            "canonical": next((l["href"] for l in doc.links if "canonical" in (l.get("rel") or "")), None),
            "lang": lang.group(1) if lang else None,
            "headings": doc.headings,
            "h1_count": sum(1 for t, _ in doc.headings if t == "h1"),
            "h2_count": sum(1 for t, _ in doc.headings if t == "h2"),
            "h3_count": sum(1 for t, _ in doc.headings if t == "h3"),
            "img_total": len(imgs),
            "img_no_alt": sum(1 for i in imgs if i["alt"] is None),
            "img_empty_alt": sum(1 for i in imgs if i["alt"] == ""),
            "img_lazy": sum(1 for i in imgs if i.get("loading") == "lazy"),
            "image_assets": sorted(img_assets, key=lambda a: -(a.get("bytes") or 0)),
            "stack": stack,
            "wp_plugins": wp_plugins(stack_html),
            "headers": home["headers"],
            "tls": tls_info(urllib.parse.urlparse(base).netloc),
        }

    report = build_report(base, perf_pages, form_pages, seo)
    with open(args.out, "w") as fh:
        fh.write(report)
    print(f"\nBericht geschrieben: {args.out}", file=sys.stderr)
    print(report)


if __name__ == "__main__":
    main()
