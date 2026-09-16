# -*- coding: utf-8 -*-
"""
SDWIS Lookup - web version.

Searches Texas public water systems by name or PWS ID.
Data: EPA Envirofacts (public). County and TCEQ region are derived from the PWS ID.
No database, no login, no private data.
"""
import csv, json, os, re, urllib.request, urllib.parse
from flask import Flask, request, Response

BASE = "https://data.epa.gov/efservice"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "tx_water_systems.csv")

ACTIVITY = {"A": "Active", "I": "Inactive",
            "N": "Changed from public to non-public",
            "M": "Merged into another system", "P": "Potential"}

_C = """Anderson Andrews Angelina Aransas Archer Armstrong Atascosa Austin Bailey Bandera
Bastrop Baylor Bee Bell Bexar Blanco Borden Bosque Bowie Brazoria
Brazos Brewster Briscoe Brooks Brown Burleson Burnet Caldwell Calhoun Callahan
Cameron Camp Carson Cass Castro Chambers Cherokee Childress Clay Cochran
Coke Coleman Collin Collingsworth Colorado Comal Comanche Concho Cooke Coryell
Cottle Crane Crockett Crosby Culberson Dallam Dallas Dawson DeafSmith Delta
Denton DeWitt Dickens Dimmit Donley Duval Eastland Ector Edwards Ellis
ElPaso Erath Falls Fannin Fayette Fisher Floyd Foard FortBend Franklin
Freestone Frio Gaines Galveston Garza Gillespie Glasscock Goliad Gonzales Gray
Grayson Gregg Grimes Guadalupe Hale Hall Hamilton Hansford Hardeman Hardin
Harris Harrison Hartley Haskell Hays Hemphill Henderson Hidalgo Hill Hockley
Hood Hopkins Houston Howard Hudspeth Hunt Hutchinson Irion Jack Jackson
Jasper JeffDavis Jefferson JimHogg JimWells Johnson Jones Karnes Kaufman Kendall
Kenedy Kent Kerr Kimble King Kinney Kleberg Knox Lamar Lamb
Lampasas LaSalle Lavaca Lee Leon Liberty Limestone Lipscomb LiveOak Llano
Loving Lubbock Lynn McCulloch McLennan McMullen Madison Marion Martin Mason
Matagorda Maverick Medina Menard Midland Milam Mills Mitchell Montague Montgomery
Moore Morris Motley Nacogdoches Navarro Newton Nolan Nueces Ochiltree Oldham
Orange PaloPinto Panola Parker Parmer Pecos Polk Potter Presidio Rains
Randall Reagan Real RedRiver Reeves Refugio Roberts Robertson Rockwall Runnels
Rusk Sabine SanAugustine SanJacinto SanPatricio SanSaba Schleicher Scurry Shackelford Shelby
Sherman Smith Somervell Starr Stephens Sterling Stonewall Sutton Swisher Tarrant
Taylor Terrell Terry Throckmorton Titus TomGreen Travis Trinity Tyler Upshur
Upton Uvalde ValVerde VanZandt Victoria Walker Waller Ward Washington Webb
Wharton Wheeler Wichita Wilbarger Willacy Williamson Wilson Winkler Wise Wood
Yoakum Young Zapata Zavala""".split()
_SPACED = {"DeafSmith": "Deaf Smith", "ElPaso": "El Paso", "FortBend": "Fort Bend",
           "JeffDavis": "Jeff Davis", "JimHogg": "Jim Hogg", "JimWells": "Jim Wells",
           "LaSalle": "La Salle", "LiveOak": "Live Oak", "PaloPinto": "Palo Pinto",
           "RedRiver": "Red River", "SanAugustine": "San Augustine",
           "SanJacinto": "San Jacinto", "SanPatricio": "San Patricio",
           "SanSaba": "San Saba", "TomGreen": "Tom Green", "ValVerde": "Val Verde",
           "VanZandt": "Van Zandt"}
COUNTY_BY_CODE = {i + 1: _SPACED.get(c, c) for i, c in enumerate(_C)}

_REGIONS = {
 1: ("Amarillo", "Armstrong Briscoe Carson Castro Childress Collingsworth Dallam DeafSmith Donley Gray Hall Hansford Hartley Hemphill Hutchinson Lipscomb Moore Ochiltree Oldham Parmer Potter Randall Roberts Sherman Swisher Wheeler"),
 2: ("Lubbock", "Bailey Cochran Crosby Dickens Floyd Garza Hale Hockley King Lamb Lubbock Lynn Motley Terry Yoakum"),
 3: ("Abilene", "Archer Baylor Brown Callahan Clay Coleman Comanche Cottle Eastland Fisher Foard Hardeman Haskell Jack Jones Kent Knox Mitchell Montague Nolan Runnels Scurry Shackelford Stephens Stonewall Taylor Throckmorton Wichita Wilbarger Young"),
 4: ("Dallas/Fort Worth", "Collin Cooke Dallas Denton Ellis Erath Fannin Grayson Hood Hunt Johnson Kaufman Navarro PaloPinto Parker Rockwall Somervell Tarrant Wise"),
 5: ("Tyler", "Anderson Bowie Camp Cass Cherokee Delta Franklin Gregg Harrison Henderson Hopkins Lamar Marion Morris Panola Rains RedRiver Rusk Smith Titus Upshur VanZandt Wood"),
 6: ("El Paso", "Brewster Culberson ElPaso Hudspeth JeffDavis Presidio"),
 7: ("Midland", "Andrews Borden Crane Dawson Ector Gaines Glasscock Howard Loving Martin Midland Pecos Reeves Terrell Upton Ward Winkler"),
 8: ("San Angelo", "Coke Concho Crockett Irion Kimble Mason McCulloch Menard Reagan Schleicher Sterling Sutton TomGreen"),
 9: ("Waco", "Bell Bosque Brazos Burleson Coryell Falls Freestone Grimes Hamilton Hill Limestone Lampasas Leon Madison McLennan Milam Mills Robertson SanSaba Washington"),
 10: ("Beaumont", "Angelina Hardin Houston Jasper Jefferson Nacogdoches Newton Orange Polk Sabine SanAugustine SanJacinto Shelby Trinity Tyler"),
 11: ("Austin", "Bastrop Blanco Burnet Caldwell Fayette Hays Lee Llano Travis Williamson"),
 12: ("Houston", "Austin Brazoria Chambers Colorado FortBend Galveston Harris Liberty Matagorda Montgomery Walker Waller Wharton"),
 13: ("San Antonio", "Atascosa Bandera Bexar Comal Edwards Frio Gillespie Guadalupe Karnes Kendall Kerr Medina Real Uvalde Wilson"),
 14: ("Corpus Christi", "Aransas Bee Calhoun DeWitt Goliad Gonzales Jackson JimWells Kleberg Lavaca LiveOak Nueces Refugio SanPatricio Victoria"),
 15: ("Harlingen", "Brooks Cameron Hidalgo JimHogg Kenedy Starr Willacy"),
 16: ("Laredo", "Dimmit Duval Kinney LaSalle Maverick McMullen ValVerde Webb Zapata Zavala"),
}
REGION_BY_COUNTY = {}
for _n, (_city, _blob) in _REGIONS.items():
    for _c in _blob.split():
        REGION_BY_COUNTY[_SPACED.get(_c, _c)] = "Region %d - %s" % (_n, _city)

_ST = (r"(?:DRIVE|DR|STREET|ST|ROAD|RD|LANE|LN|CIRCLE|CIR|AVENUE|AVE|BOULEVARD|BLVD|COURT|CT|"
       r"PARKWAY|PKWY|TRAIL|TRL|TERRACE|TER|PLACE|PL|HIGHWAY|HWY|LOOP|WAY|RUN|BEND|PASS|PATH|COVE|CV)")
_HWY = r"(?:SH|FM|RM|US|IH|CR|PR|SL|BU|TX|HWY)\s*-?\s*\d{1,4}"
_SPEC = re.compile(r"\b(?:MG|MGD|GPM|GAL|HP|PSI|GR|HD|SP|PF|GS|SW|GW|LOT)\b", re.I)
_TYPEWORD = re.compile(r"\b(?:PLANT|WELL|TANK|INTAKE|DISTRIBUTION|SYSTEM|BOOSTER|PUMP|SWTP|GWTP|WTP|"
                       r"ABANDONED|TAP|INTERCONNECT|EMERGENCY|PRESSURE|PLANE)\b", re.I)
_ADDR = re.compile(r"\d{1,6}\s+[A-Z0-9][A-Z0-9'\.\s]{1,28}?\s+" + _ST + r"\b", re.I)
_ADDR_NONUM = re.compile(r"\b[A-Z][A-Z0-9'\.]{2,}(?:\s+[A-Z0-9'\.]{2,}){0,3}\s+" + _ST + r"\b", re.I)
_HWY_RE = re.compile(r"(?:\d{1,6}\s+)?" + _HWY + r"(?:\s*/\s*(?:" + _HWY + r"|\d{1,4}))?", re.I)
_CITY = re.compile(r"[;,]\s*([A-Z][A-Z\s]{2,24})\s*$", re.I)


def _tidy(s):
    return re.sub(r"\s{2,}", " ", s).strip(" -;,/.").upper()


def _ok(s):
    return bool(s) and len(s) >= 5 and not _SPEC.search(s) and not _TYPEWORD.search(s)


def addresses(names):
    found = []
    for nm in names:
        nm = (nm or "").strip()
        if not nm:
            continue
        nm = re.sub(r"^[NSEW]{1,2}\s+SIDE\s+OF\s+", "", nm, flags=re.I)
        for rx in (_ADDR, _HWY_RE, _ADDR_NONUM):
            for m in rx.finditer(nm):
                c = _tidy(m.group(0))
                if _ok(c):
                    found.append(c)
            if found and rx is _ADDR:
                break
    seen, out = set(), []
    for a in found:
        k = re.sub(r"[^A-Z0-9]", "", a)
        if k and k not in seen:
            seen.add(k)
            out.append(a)
    out.sort(key=lambda s: (0 if re.match(r"^\d", s) else 1, -len(s)))
    return out


def city_from(names):
    hits = []
    for nm in names:
        m = _CITY.search((nm or "").strip())
        if m:
            c = _tidy(m.group(1))
            if _ok(c) and not re.search(r"\b" + _ST + r"\b", c, re.I):
                hits.append(c)
    return max(set(hits), key=hits.count) if hits else ""


def maps_url(address, city, county):
    where = city or ((county + " County") if county else "")
    q = ", ".join(x for x in (address, where, "TX") if x)
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(q)


def county_from_pws(pwsid):
    d = re.sub(r"[^0-9]", "", str(pwsid))
    if len(d) == 8 and d.startswith("0"):
        d = d[1:]
    if len(d) < 7:
        d = d.zfill(7)
    return COUNTY_BY_CODE.get(int(d[:3]), "") if len(d) == 7 else ""


def _get(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def facilities(digits):
    try:
        return json.loads(_get("%s/WATER_SYSTEM_FACILITY/PWSID/TX%s/JSON" % (BASE, digits)))
    except Exception:
        return []


def geographic(digits):
    try:
        ga = json.loads(_get("%s/GEOGRAPHIC_AREA/PWSID/TX%s/JSON" % (BASE, digits)))
        return ga[0] if ga else {}
    except Exception:
        return {}




CENSUS = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def geocode(addr):
    """US Census geocoder: free, no key, US addresses only. Returns (lat, lon, matched) or None."""
    q = urllib.parse.urlencode({"address": addr, "benchmark": "Public_AR_Current", "format": "json"})
    try:
        raw = _get(CENSUS + "?" + q, 25)
        m = (json.loads(raw).get("result") or {}).get("addressMatches") or []
        if not m:
            return None
        c = m[0]["coordinates"]
        return round(float(c["y"]), 6), round(float(c["x"]), 6), m[0].get("matchedAddress", "")
    except Exception:
        return None


def ranked_addresses(names):
    """Addresses with a repeat count, best first: most repeats, then house-numbered, then longest."""
    hits = []
    for nm in names:
        nm = (nm or "").strip()
        if not nm:
            continue
        nm = re.sub(r"^[NSEW]{1,2}\s+SIDE\s+OF\s+", "", nm, flags=re.I)
        for rx in (_ADDR, _HWY_RE, _ADDR_NONUM):
            found_here = False
            for m in rx.finditer(nm):
                c = _tidy(m.group(0))
                if _ok(c):
                    hits.append(c)
                    found_here = True
            if found_here and rx is _ADDR:
                break
    counts = {}
    for a in hits:
        k = re.sub(r"[^A-Z0-9]", "", a)
        if k not in counts:
            counts[k] = [a, 0]
        counts[k][1] += 1
    out = list(counts.values())
    out.sort(key=lambda p: (0 if p[0][:1].isdigit() else 1, -p[1], -len(p[0])))
    return out


def duo_maps_url(lat, lon, label):
    lab = urllib.parse.quote(label)
    return ("https://puctx.maps.arcgis.com/apps/mapviewer/index.html"
            "?webmap=e9053b2e598e41d4b593fbe1483046fa"
            "&center=%s,%s&level=15&marker=%s;%s;4326;%s;;%s" % (lon, lat, lon, lat, lab, lab))


def gmaps_coords(lat, lon):
    return "https://www.google.com/maps/search/?api=1&query=%s,%s" % (lat, lon)


ROWS = []
if os.path.exists(CACHE):
    with open(CACHE, newline="", encoding="utf-8") as f:
        ROWS = list(csv.DictReader(f))

app = Flask(__name__)


def search(term):
    t = (term or "").strip()
    if not t:
        return []
    digits = re.sub(r"[^0-9]", "", t)
    if digits and len(digits) >= 6 and not re.search(r"[A-Za-z]{2,}", t):
        want = digits.zfill(7)
        return [r for r in ROWS if re.sub(r"[^0-9]", "", r.get("pwsid") or "")[-7:] == want]
    low = t.lower()
    return [r for r in ROWS if low in (r.get("pws_name") or "").lower()]


def esc(s):
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --navy:#16304f; --navy2:#1f4670; --ink:#16202b; --mute:#63707f;
  --line:#e2e6ec; --bg:#f2f4f7; --card:#fff; --accent:#1f4670;
}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);
  font:400 15.5px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
header{background:var(--navy);color:#fff;padding:26px 20px 30px;
  background-image:linear-gradient(180deg,#1b3a5e 0%,#16304f 100%)}
.hwrap{max-width:860px;margin:0 auto}
header h1{margin:0;font-size:20px;font-weight:600;letter-spacing:-.1px}
header .sub{margin:6px 0 0;font-size:13px;line-height:1.5;color:#b9c8d9}
.wrap{max-width:860px;margin:0 auto;padding:0 20px 72px}
form{display:flex;gap:10px;margin:-18px 0 24px;background:var(--card);padding:10px;
  border:1px solid var(--line);border-radius:10px;box-shadow:0 4px 18px rgba(16,32,48,.10)}
input[type=text]{flex:1;min-width:0;border:1px solid var(--line);border-radius:7px;
  padding:11px 13px;font-size:15.5px;color:var(--ink);background:#fcfdfe}
input[type=text]::placeholder{color:#93a0ae}
input[type=text]:focus{outline:none;border-color:var(--navy2);box-shadow:0 0 0 3px rgba(31,70,112,.14)}
button{flex:0 0 auto;background:var(--navy2);color:#fff;border:0;border-radius:7px;
  padding:11px 22px;font-size:15px;font-weight:500;cursor:pointer;transition:background .12s}
button:hover{background:var(--navy)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:20px 22px;margin-bottom:16px;box-shadow:0 1px 2px rgba(16,32,48,.04)}
.card.accent{border-left:3px solid var(--accent)}
.hd{border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:4px}
.hd h2{margin:0;font-size:18.5px;font-weight:600;letter-spacing:-.15px;line-height:1.3}
.pwsid{margin-top:3px;font:12.5px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace;
  color:var(--mute);letter-spacing:.3px}
h3{margin:22px 0 8px;font-size:11.5px;font-weight:600;text-transform:uppercase;
  letter-spacing:.9px;color:var(--mute)}
.card.accent h3{margin-top:0}
table.kv{border-collapse:collapse;width:100%}
table.kv td{padding:7px 0;vertical-align:top;font-size:14.5px;border-bottom:1px solid #f0f2f5}
table.kv tr:last-child td{border-bottom:0}
td.k{width:210px;padding-right:16px;color:var(--mute);font-size:13.5px}
td.v{word-break:break-word}
.mono{font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}
.pill{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11.5px;
  font-weight:600;letter-spacing:.2px;vertical-align:1px}
.on{background:#e6f4ea;color:#1a6b39}
.off{background:#fdecec;color:#9b2c2c}
.warn{margin-top:14px;padding:11px 13px;border-radius:7px;font-size:13.5px;line-height:1.5;
  background:#fff8e6;color:#7a5200;border:1px solid #f3e2b8}
.note{margin:14px 0 0;font-size:12.5px;line-height:1.55;color:var(--mute)}
a{color:var(--navy2);text-decoration:none;border-bottom:1px solid rgba(31,70,112,.28)}
a:hover{border-bottom-color:var(--navy2)}
.links a{margin-right:18px;font-size:14px;white-space:nowrap}
ul.hits{list-style:none;padding:0;margin:0}
ul.hits li{padding:12px 0;border-bottom:1px solid #f0f2f5}
ul.hits li:last-child{border-bottom:0}
ul.hits .nm{font-size:15px;font-weight:500}
.muted{color:var(--mute);font-size:13.5px}
.count{font-size:12px;color:var(--mute);margin-left:6px}
footer{max-width:860px;margin:0 auto;padding:4px 20px;font-size:12px;line-height:1.6;
  color:#7d8996;text-align:center}
@media(max-width:600px){
  form{flex-direction:column;margin-top:-14px}
  td.k{width:135px;font-size:13px}
  .wrap,.hwrap,footer{padding-left:14px;padding-right:14px}
  .links a{display:block;margin:0 0 7px}
}
"""

PAGE = """<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>SDWIS Lookup - Texas water systems</title><style>%s</style>
<header><h1>SDWIS Lookup</h1>
<p>Texas public water systems &middot; EPA Envirofacts &middot; county and TCEQ region derived from the PWS ID</p></header>
<div class=wrap>
<form method=get action="/">
<input type=text name=q placeholder="PWS ID (0270008) or system name (Stone Hedge)" value="%s" autofocus>
<button type=submit>Search</button></form>
%s
<footer>Public EPA data &middot; EPA lags TCEQ by about a quarter<br>
Coordinates are geocoded from addresses recorded in EPA facility names</footer>
</div></html>"""


def render_one(rec):
    pid = (rec.get("pwsid") or "").strip()
    digits = re.sub(r"[^0-9]", "", pid)[-7:]
    act = (rec.get("pws_activity_code") or "").strip()
    dea = (rec.get("pws_deactivation_date") or "")[:10]
    county = county_from_pws(digits)
    region = REGION_BY_COUNTY.get(county, "")
    cls = "on" if act == "A" else "off"

    ga = geographic(digits)
    epa_county = (ga.get("county_served") or "").strip()
    mismatch = epa_county and county and epa_county.lower() != county.lower()

    names = [f.get("facility_name") for f in facilities(digits)]
    town = city_from(names)

    def row(k, v, mono=False):
        cl = " class=mono" if mono else ""
        return '<tr><td class=k>%s</td><td class=v%s>%s</td></tr>' % (esc(k), cl, v)

    h = ['<div class=card>',
         '<div class=hd><h2>%s</h2><div class=pwsid>%s</div></div>'
         % (esc(rec.get("pws_name") or ""), esc(pid)),
         '<table class=kv>']
    status = '<span class="pill %s">%s</span>' % (cls, esc(ACTIVITY.get(act, act or "unknown")))
    if dea and act != "A":
        status += ' <span class=muted>deactivated %s</span>' % esc(dea)
    h.append(row("Activity", status))
    h.append(row("System type", esc(rec.get("pws_type_code") or "&mdash;")))
    h.append(row("Owner type", esc(rec.get("owner_type_code") or "&mdash;")))
    h.append(row("Population served", esc(rec.get("population_served_count") or "&mdash;")))
    if epa_county:
        h.append(row("County (EPA record)", esc(epa_county)))
    if town:
        h.append(row("City", esc(town)))
    h.append('</table>')
    if mismatch:
        h.append('<div class=warn><strong>County mismatch.</strong> The PWS ID prefix indicates %s, '
                 'but EPA records %s. The ID may be mistyped.</div>' % (esc(county), esc(epa_county)))

    ranked = ranked_addresses(names)
    if ranked:
        h.append('<h3>Addresses in facility names</h3><table class=kv>')
        for a, cnt in ranked[:3]:
            tag = '<span class=count>&times;%d</span>' % cnt if cnt > 1 else ''
            h.append('<tr><td class=v colspan=2>%s%s</td></tr>' % (esc(a), tag))
        h.append('</table>')

    h.append('<h3>References</h3><div class=links>'
             '<a href="https://dwv.tceq.texas.gov/home/TX%s" target=_blank rel=noopener>TCEQ Drinking Water Viewer</a>'
             '<a href="https://sdwis.epa.gov/ords/sfdw_pub/f?p=108:200:::NO:200:P200_PWSID:TX%s" '
             'target=_blank rel=noopener>EPA SDWIS record</a></div>' % (digits, digits))
    h.append('</div>')

    lat = lon = matched = best = ""
    where = town or ((county + " County") if county else "")
    for cand, _cnt in ranked[:4]:
        g = geocode(", ".join(x for x in (cand, where, "TX") if x))
        if g:
            best, lat, lon, matched = cand, str(g[0]), str(g[1]), g[2]
            break

    pop_raw = re.sub(r"[^0-9]", "", str(rec.get("population_served_count") or ""))
    est_shown = bool(pop_raw) and int(pop_raw) > 0

    h.append('<div class="card accent"><h3>Derived Values</h3><table class=kv>')
    h.append(row("County", esc(county or "&mdash;")))
    h.append(row("TCEQ Region", esc(region or "&mdash;")))
    if est_shown:
        h.append(row("Connections", str(int(round(int(pop_raw) / 3.0))), mono=True))
    if lat:
        h.append(row("Latitude", esc(lat), mono=True))
        h.append(row("Longitude", esc(lon), mono=True))
    gm = (gmaps_coords(lat, lon) if lat else
          ("https://www.google.com/maps/search/?api=1&query="
           + urllib.parse.quote_plus(county + " County, TX") if county else ""))
    dm = (duo_maps_url(lat, lon, rec.get("pws_name") or "") if lat else
          ("https://puctx.maps.arcgis.com/apps/mapviewer/index.html"
           "?webmap=e9053b2e598e41d4b593fbe1483046fa" if county else ""))
    for k, u in (("Google Maps link", gm), ("DUO Maps", dm)):
        if u:
            h.append(row(k, '<a class=mono href="%s" target=_blank rel=noopener>%s</a>'
                         % (esc(u), esc(u))))
    h.append('</table>')

    prov = ["County and TCEQ region are derived from the PWS ID prefix."]
    if est_shown:
        prov.append("Connections is an estimate, population divided by 3, not a measured count.")
    if matched:
        prov.append("Coordinates were geocoded from %s." % matched)
    elif county:
        prov.append("No street address was found, so the map links fall back to county level.")
    h.append('<p class=note>%s</p>' % esc(" ".join(prov)))
    h.append('</div>')
    return "".join(h)


@app.route("/")
def home():
    q = request.args.get("q", "")
    body = ""
    if q.strip():
        hits = search(q)
        if not hits:
            d = re.sub(r"[^0-9]", "", q)
            extra = ""
            if len(d) >= 7:
                c = county_from_pws(d)
                if c:
                    extra = (" That ID's prefix points to %s County, so it may be mistyped."
                             % esc(c))
            body = '<div class=card><b>No match.</b>%s</div>' % extra
        elif len(hits) > 60:
            body = ('<div class=card><b>%d matches.</b> Narrow the search.</div>' % len(hits))
        elif len(hits) == 1:
            body = render_one(hits[0])
        else:
            li = []
            for r in hits:
                act = (r.get("pws_activity_code") or "").strip()
                li.append('<li><a class=nm href="/?q=%s">%s</a> <span class=pwsid>%s</span><br>'
                          '<span class=muted>%s</span></li>'
                          % (esc(re.sub(r"[^0-9]", "", r.get("pwsid") or "")[-7:]),
                             esc(r.get("pws_name") or ""), esc(r.get("pwsid") or ""),
                             esc(ACTIVITY.get(act, act))))
            body = ('<div class=card><h3 style="margin-top:0">%d matches</h3>'
                    '<ul class=hits>%s</ul></div>' % (len(hits), "".join(li)))
    else:
        body = ('<div class=card class=muted><b>%d Texas water systems loaded.</b><br>'
                '<span class=muted>Search by PWS ID or part of a system name. County and TCEQ '
                'region come from the first three digits of the PWS ID, so a county that '
                'disagrees flags a likely typo.</span></div>' % len(ROWS))
    return Response(PAGE % (CSS, esc(q), body), mimetype="text/html")


@app.route("/health")
def health():
    return {"ok": True, "systems": len(ROWS)}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
