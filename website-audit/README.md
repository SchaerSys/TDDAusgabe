# Website-Audit tischlein-deckdich.at

Technisches Pruefprotokoll zu Performance, Formular-Datenschutz und SEO
der Vereinswebsite.

## Erzeugung

    python3 website_audit.py https://www.tischlein-deckdich.at \
        --start / \
        --ausgabestellen /ausgabestellen/ \
        --formular /volunteer-bewerbung-bei-fahrer-in/ \
        --formular /volunteer-bewerbung-lagerhilfskraft-vandans/ \
        --formular /volunteer-bewerbung-ausgabe-dornbirn/ \
        --formular /kontaktformular/ \
        --out pruefprotokoll.md

Voraussetzungen: python3, curl, openssl.

Das Skript ist strikt lesend: es sendet ausschliesslich GET- und
HEAD-Requests. Formulare werden nur im HTML-Quelltext analysiert und
nie abgesendet - es wurde kein Datensatz angelegt und keine Mail
ausgeloest.

Die geprueften Pfade stammen aus der Sitemap der Website, nicht aus den
Beispielpfaden im Kopf des Skripts.

## Belastbarkeit der Werte

Der Lauf erfolgte hinter einem TLS-terminierenden Proxy. Daraus folgt:

- **Nicht belastbar:** absolute TTFB- und Ladezeitwerte (enthalten
  Proxy-Laufzeit), die ausgewiesene Server-IP, die HTTP-Version sowie
  die Zertifikatsangaben. Diese Punkte sind von einem normalen
  Netzzugang nachzumessen.
- **Belastbar:** Formular- und HTML-Analyse, Antwort-Header
  (Cache-Control, Kompression, Security-Header), Ressourcengroessen
  und die SEO- bzw. Barrierefreiheitsmerkmale. Ebenso die Vergleiche
  zwischen den Seiten dieses Berichts, da alle denselben Netzweg nutzen.

Core Web Vitals (LCP, CLS, INP) sind mit curl grundsaetzlich nicht
messbar und ueber PageSpeed Insights zu ergaenzen.

## Wichtigster Befund

Alle sechs Bewerbungsformulare fragen die Sozialversicherungsnummer als
Pflichtfeld ab ("Bitte geben Sie Ihre 10-stellige
Sozialversicherungsnummer hier ein"). Fuer eine Erstbewerbung von
Freiwilligen ist sie regelmaessig nicht erforderlich; die Erhebung
widerspricht der Datenminimierung nach Art. 5 Abs. 1 lit. c DSGVO.
Details in Abschnitt 2 des Protokolls.
