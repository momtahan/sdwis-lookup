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
*{box-sizing:border-box}
body{margin:0;font:16px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
     background:#f4f5f7;color:#1b2430}
header{background:#1f3864;color:#fff;padding:22px 18px}
header h1{margin:0;font-size:21px;letter-spacing:.2px}
header p{margin:5px 0 0;font-size:13px;opacity:.82}
.wrap{max-width:820px;margin:0 auto;padding:20px 18px 64px}
form{display:flex;gap:9px;margin:-32px 0 22px;background:#fff;padding:11px;border-radius:11px;
     box-shadow:0 3px 14px rgba(0,0,0,.11)}
input[type=text]{flex:1;border:1px solid #d3d8e0;border-radius:7px;padding:12px 13px;font-size:16px;min-width:0}
input[type=text]:focus{outline:2px solid #2e5496;border-color:transparent}
button{background:#1f3864;color:#fff;border:0;border-radius:7px;padding:12px 22px;font-size:15px;cursor:pointer}
button:hover{background:#2e5496}
.card{background:#fff;border-radius:11px;padding:19px 21px;margin-bottom:15px;
      box-shadow:0 1px 4px rgba(0,0,0,.09)}
.card h2{margin:0 0 3px;font-size:19px}
.pwsid{font:13px ui-monospace,Consolas,monospace;color:#5b6675}
table{border-collapse:collapse;width:100%;margin:13px 0 0}
td{padding:5px 0;vertical-align:top;font-size:14.5px}
td.k{color:#5b6675;width:190px;padding-right:12px}
.tag{display:inline-block;padding:2px 9px;border-radius:11px;font-size:12px;font-weight:600}
.on{background:#e3f4e8;color:#1c6b34}.off{background:#fdeaea;color:#a12b2b}
.warn{background:#fff6e0;color:#8a5b00;padding:9px 12px;border-radius:7px;font-size:13.5px;margin-top:12px}
h3{margin:19px 0 7px;font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:#5b6675}
a{color:#2e5496}
ul.hits{list-style:none;padding:0;margin:0}
ul.hits li{padding:11px 0;border-bottom:1px solid #eceef2}
ul.hits li:last-child{border:0}
.muted{color:#5b6675;font-size:13.5px}
footer{margin-top:26px;font-size:12.5px;color:#5b6675;text-align:center}
@media(max-width:560px){td.k{width:132px}form{flex-direction:column}}
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
<footer>Public EPA data. EPA lags TCEQ by about a quarter.<br>
Coordinates are not published by any public source &mdash; addresses below are read out of facility names.</footer>
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
    addrs, town = addresses(names), city_from(names)

    rows = [("Activity", '<span class="tag %s">%s</span>%s' % (
                cls, esc(ACTIVITY.get(act, act or "unknown")),
                (" deactivated " + esc(dea)) if dea and act != "A" else "")),
            ("System type", esc(rec.get("pws_type_code") or "?")),
            ("Owner type", esc(rec.get("owner_type_code") or "?")),
            ("Population served", esc(rec.get("population_served_count") or "?")),
            ("County (from PWS ID)", esc(county or "?")),
            ("TCEQ region", esc(region or "?"))]
    if epa_county:
        rows.append(("County (EPA)", esc(epa_county)))
    if town:
        rows.append(("City", esc(town)))

    h = ['<div class=card><h2>%s</h2><div class=pwsid>%s</div><table>' % (
         esc(rec.get("pws_name") or ""), esc(pid))]
    for k, v in rows:
        h.append("<tr><td class=k>%s</td><td>%s</td></tr>" % (esc(k), v))
    h.append("</table>")
    if mismatch:
        h.append('<div class=warn><b>County mismatch.</b> The PWS ID prefix gives %s but EPA '
                 'records %s. The ID may be mistyped.</div>' % (esc(county), esc(epa_county)))

    h.append("<h3>Links</h3>")
    h.append('<div><a href="https://dwv.tceq.texas.gov/home/TX%s" target=_blank rel=noopener>TCEQ Drinking Water Viewer</a>'
             ' &middot; <a href="https://sdwis.epa.gov/ords/sfdw_pub/f?p=108:200:::NO:200:P200_PWSID:TX%s" '
             'target=_blank rel=noopener>EPA SDWIS page</a></div>' % (digits, digits))

    if addrs:
        h.append("<h3>Location from facility names</h3><div>")
        for a in addrs[:3]:
            h.append('<div><a href="%s" target=_blank rel=noopener>%s</a></div>'
                     % (esc(maps_url(a, town, county)), esc(a)))
        h.append("</div>")
    elif names:
        h.append('<div class=muted style="margin-top:12px">No address-like facility name '
                 'found (%d facilities checked).</div>' % len(names))
    h.append("</div>")
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
                li.append('<li><a href="/?q=%s">%s</a> <span class=pwsid>%s</span><br>'
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
