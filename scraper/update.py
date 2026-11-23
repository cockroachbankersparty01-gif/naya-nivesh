#!/usr/bin/env python3
"""Naya Nivesh data updater.

Runs on GitHub Actions (no Claude, no paid API). Reads docs/data.json, collects the
latest public IPO data and writes the file back:

  * IPO discovery, price band, lot, issue size, dates, KPIs, peers,
    category-wise subscription and day-wise GMP  -> gmpipowatch.in IPO pages
  * extra GMP quotes (fallback)                  -> ipowatch.in GMP table
  * overall subscription, listing-day open/close -> NSE public JSON endpoints

Every source is optional: if a site is down, blocks the runner or changes its layout,
the script logs a warning and keeps the previous values. It never deletes data it
could not refresh. Values are only written when they parse as numbers/dates.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOW = dt.datetime.now(IST)
TODAY = NOW.date()
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}
GP = "https://www.gmpipowatch.in"
REGISTRARS = ["KFin Technologies", "MUFG Intime", "Bigshare Services", "Maashitla Securities",
              "Cameo Corporate", "Skyline Financial", "Purva Sharegistry", "MAS Services"]
MON = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

ok_sources: set[str] = set()


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- helpers
def num(s):
    """'₹1,234.5 Cr' -> 1234.5 ; '-' / '' / None -> None ; '(12.3)' -> -12.3"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).replace(",", "").replace("₹", "").replace("Rs.", "").strip()
    neg = t.startswith("(") and t.endswith(")")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    v = float(m.group())
    return -abs(v) if neg else v


def clean_name(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    s = re.sub(r"\b(IPO|SME|NSE|BSE|Emerge|Mainboard|Ltd\.?|Limited|Upcoming|Open|Closed|Listed)\b",
               "", s, flags=re.I)
    s = re.sub(r"[\(\)\[\]]", " ", s)
    return re.sub(r"\s+", " ", s).strip(" -–·")


def slugify(s: str) -> str:
    s = clean_name(s).lower().replace("&", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def parse_date(s):
    """'19 Nov 2026', '19-Nov-2026', '2026-11-19', '19/11/2026' -> 'YYYY-MM-DD'"""
    if not s:
        return None
    s = str(s).strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    m = re.search(r"(\d{1,2})[\s\-/]+([A-Za-z]{3})[A-Za-z]*[\s\-/,]+(\d{2,4})", s)
    if m and m.group(2).lower() in MON:
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        return f"{y:04d}-{MON[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[A-Za-z]*\b", s)  # '19 Nov' (no year)
    if m and m.group(2).lower() in MON:
        d = dt.date(TODAY.year, MON[m.group(2).lower()], int(m.group(1)))
        if (d - TODAY).days > 200:
            d = d.replace(year=d.year - 1)
        return d.isoformat()
    return None


def get(url, session=None, **kw):
    s = session or requests
    for attempt in range(2):
        try:
            r = s.get(url, headers=UA, timeout=25, **kw)
            if r.status_code == 200:
                return r
            log(f"  {r.status_code} {url}")
            if r.status_code in (403, 404):
                return None
        except requests.RequestException as e:
            log(f"  error {url}: {e.__class__.__name__}")
        time.sleep(2)
    return None


def tables(soup):
    """All HTML tables as (headers, rows) with cell text."""
    out = []
    for t in soup.find_all("table"):
        rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])] for tr in t.find_all("tr")]
        rows = [r for r in rows if any(r)]
        if len(rows) < 2:
            continue
        out.append(([h.lower() for h in rows[0]], rows[1:]))
    return out


def col(headers, *keys, avoid=()):
    for i, h in enumerate(headers):
        if any(k in h for k in keys) and not any(a in h for a in avoid):
            return i
    return None


def label_value(text, *labels):
    """Find 'Label: value' or 'Label  value' in page text."""
    for lab in labels:
        m = re.search(re.escape(lab) + r"\s*[:\-]?\s*([^\n]{1,60})", text, re.I)
        if m and m.group(1).strip() not in ("", "-", "TBA", "[●]"):
            return m.group(1).strip()
    return None


# ---------------------------------------------------------------- gmpipowatch
def gp_discover():
    """IPO slugs listed on gmpipowatch overview pages, with segment and status hints."""
    found = {}
    for path, seg in (("/", None), ("/mainboard", "Mainboard"), ("/sme", "SME")):
        r = get(GP + path)
        if not r:
            continue
        ok_sources.add("gmpipowatch")
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.find_all("a", href=True):
            m = re.fullmatch(r"(?:https://www\.gmpipowatch\.in)?/ipo/([a-z0-9\-]+)/?", a["href"])
            if not m:
                continue
            row = a.find_parent("tr")
            ctx = row.get_text(" ", strip=True) if row else a.get_text(" ", strip=True)
            st = next((w for w in ("Open", "Upcoming", "Closed", "Listed") if re.search(rf"\b{w}\b", ctx)), None)
            sg = seg or ("SME" if re.search(r"\bSME\b", ctx) else ("Mainboard" if "Mainboard" in ctx else None))
            f = found.setdefault(m.group(1), {"slug": m.group(1), "seg": sg, "status": st})
            f["seg"] = f["seg"] or sg
            f["status"] = f["status"] or st
    log(f"gmpipowatch discovery: {len(found)} IPO links")
    return found


def gp_detail(slug):
    r = get(f"{GP}/ipo/{slug}")
    if not r:
        return None
    ok_sources.add("gmpipowatch")
    soup = BeautifulSoup(r.text, "lxml")
    text = soup.get_text("\n", strip=True)
    d = {"slug": slug, "url": f"{GP}/ipo/{slug}"}
    h1 = soup.find("h1")
    d["name"] = clean_name(re.sub(r"(GMP|Today|Grey Market Premium).*$", "", h1.get_text(" ", strip=True), flags=re.I)) if h1 else None
    d["seg"] = "SME" if re.search(r"\bSME IPO\b|classified as a SME|NSE SME|BSE SME|Emerge", text) else "Mainboard"
    band = label_value(text, "IPO Price Band", "Price Band")
    if band:
        vals = [num(x) for x in re.findall(r"₹?\s*([\d,]+(?:\.\d+)?)", band)]
        vals = [v for v in vals if v]
        if vals:
            d["band"] = [min(vals), max(vals)]
    lot = num(label_value(text, "Lot Size"))
    if lot and lot >= 1:
        d["lot"] = int(lot)
    size = label_value(text, "Issue Size")
    if size and "cr" in size.lower():
        d["issueCr"] = num(size)
    fresh = label_value(text, "Fresh Issue")
    if fresh and "cr" in fresh.lower():
        d["freshCr"] = num(fresh)
    for k, labs in (("open", ("IPO Open Date", "Open Date")), ("close", ("IPO Close Date", "Close Date")),
                    ("allot", ("Basis of Allotment", "Allotment Date")), ("refund", ("Initiation of Refunds", "Refund")),
                    ("list", ("Listing Date",))):
        v = parse_date(label_value(text, *labs))
        if v:
            d.setdefault("dates", {})[k] = v
    reg = label_value(text, "Registrar")
    if reg:
        for R in REGISTRARS:
            if R.split()[0].lower() in reg.lower():
                d["registrar"] = R
    m = re.search(r"Listing (?:Open|Price|Day Open)[^\n₹]{0,40}₹\s*([\d,]+(?:\.\d+)?)", text, re.I)
    if m:
        d["listOpen"] = num(m.group(1))

    for hd, rows in tables(soup):
        # GMP trend: Date | GMP | ...
        if col(hd, "date") is not None and col(hd, "gmp") is not None and col(hd, "category") is None:
            di, gi = col(hd, "date"), col(hd, "gmp", avoid=("%",))
            pts = []
            for r_ in rows:
                if gi is None or max(di, gi) >= len(r_):
                    continue
                dd, gv = parse_date(r_[di]), num(r_[gi])
                if dd and gv is not None and abs(gv) < 100000:
                    pts.append({"d": dd, "v": gv})
            if pts:
                d["gmp"] = pts
        # Subscription: Category | ... | Subscription (x)
        elif col(hd, "category") is not None and col(hd, "subscription", "times", "(x)") is not None:
            ci, si = col(hd, "category"), col(hd, "subscription", "times", "(x)")
            sub = {}
            for r_ in rows:
                if max(ci, si) >= len(r_):
                    continue
                c, v = r_[ci].lower(), num(r_[si])
                if v is None:
                    continue
                if "qib" in c or "qualified" in c: sub["qib"] = v
                elif "nii" in c or "non" in c or "hni" in c: sub.setdefault("nii", v)
                elif "retail" in c or "individual" in c or "rii" in c: sub["rii"] = v
                elif "employee" in c: sub["emp"] = v
                elif "shareholder" in c: sub["sh"] = v
                elif "total" in c or "overall" in c: sub["total"] = v
            if sub.get("total") is not None:
                d["sub"] = sub
        # KPIs: KPI | Values
        elif col(hd, "kpi") is not None:
            for r_ in rows:
                if len(r_) < 2:
                    continue
                k, v = r_[0].lower(), num(r_[1])
                if v is None:
                    continue
                if k.startswith("roe"): d["roe"] = v
                elif "roce" in k: d["roce"] = v
                elif "ronw" in k: d["ronw"] = v
                elif "ebitda" in k: d["ebitdaM"] = v
                elif "pat margin" in k: d["patM"] = v
                elif "debt" in k: d["de"] = v
                elif "eps" in k or "earning" in k: d["eps"] = v
                elif "p/e" in k or "pe ratio" in k: d["pe"] = v
                elif "nav" in k: d["nav"] = v
                elif "market cap" in k: d["mcapCr"] = v
        # Peers: Company | EPS | P/E | RoNW ...
        elif col(hd, "company", "name") is not None and col(hd, "p/e", "pe") is not None and col(hd, "ronw", "eps") is not None:
            ni, pi, ri = col(hd, "company", "name"), col(hd, "p/e", "pe"), col(hd, "ronw")
            peers = []
            for r_ in rows:
                if ni >= len(r_) or slugify(r_[ni]) == slug:
                    continue
                peers.append({"n": clean_name(r_[ni]),
                              "pe": num(r_[pi]) if pi is not None and pi < len(r_) else None,
                              "ronw": num(r_[ri]) if ri is not None and ri < len(r_) else None})
            if peers:
                d["peers"] = peers
        # Financials: rows are periods, or first column holds 'Revenue', 'Profit After Tax'
        elif any("revenue" in h for h in hd) or any(r_ and "revenue" in r_[0].lower() for r_ in rows):
            fin = parse_fin(hd, rows)
            if fin:
                d["fin"] = fin
    return d


def fy_label(s):
    p = parse_date(s)
    if p:
        y, m = int(p[:4]), int(p[5:7])
        return f"FY{(y if m <= 3 else y + 1) % 100:02d}" if m == 3 else f"{dt.date(y, m, 1):%b %Y}"
    m = re.search(r"FY\s?'?(\d{2,4})", s, re.I)
    return f"FY{int(m.group(1)) % 100:02d}" if m else None


def parse_fin(hd, rows):
    out = {}
    def put(per, key, v):
        lab = fy_label(per)
        if lab and v is not None:
            out.setdefault(lab, {"y": lab})[key] = v
    keymap = (("revenue", "rev"), ("total income", "rev"), ("profit after tax", "pat"), ("pat", "pat"),
              ("net worth", "nw"), ("ebitda", "ebitda"), ("assets", "assets"))
    if any("revenue" in h or "profit" in h for h in hd):          # periods as rows
        for r_ in rows:
            for i, h in enumerate(hd):
                for kw, k in keymap:
                    if kw in h and i < len(r_):
                        put(r_[0], k, num(r_[i])); break
    else:                                                          # periods as columns
        for r_ in rows:
            lab = r_[0].lower()
            for kw, k in keymap:
                if kw in lab:
                    for i in range(1, min(len(r_), len(hd))):
                        put(hd[i], k, num(r_[i]))
                    break
    rows_ = [v for v in out.values() if v.get("rev") is not None or v.get("pat") is not None]
    rows_.sort(key=lambda r: (0 if r["y"].startswith("FY") else 1, r["y"]))
    return rows_ or None


# ---------------------------------------------------------------- ipowatch GMP table (fallback)
def ipowatch_gmp():
    out = {}
    for url in ("https://ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/",):
        r = get(url)
        if not r:
            continue
        for hd, rows in tables(BeautifulSoup(r.text, "lxml")):
            ni, gi = col(hd, "ipo", "name", "company"), col(hd, "gmp", avoid=("%", "date"))
            if ni is None or gi is None:
                continue
            for r_ in rows:
                if max(ni, gi) < len(r_) and num(r_[gi]) is not None:
                    out[slugify(r_[ni])] = num(r_[gi])
        if out:
            ok_sources.add("ipowatch")
    log(f"ipowatch GMP table: {len(out)} quotes")
    return out


# ---------------------------------------------------------------- NSE
class NSE:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(UA | {"Referer": "https://www.nseindia.com/market-data/all-upcoming-issues-ipo",
                                    "Accept": "application/json, text/plain, */*"})
        self.ok = bool(get("https://www.nseindia.com/market-data/all-upcoming-issues-ipo", self.s))

    def api(self, path):
        if not self.ok:
            return None
        r = get("https://www.nseindia.com/api/" + path, self.s)
        try:
            j = r.json() if r else None
            if j is not None:
                ok_sources.add("nse")
            return j
        except ValueError:
            return None

    def issues(self):
        out = []
        for p in ("ipo-current-issue", "all-upcoming-issues?category=ipo"):
            j = self.api(p)
            if isinstance(j, dict):
                j = j.get("data") or j.get("activeIssues") or []
            if isinstance(j, list):
                out += [x for x in j if isinstance(x, dict)]
        log(f"NSE issues: {len(out)}")
        return out

    def listing(self, symbol):
        j = self.api(f"quote-equity?symbol={requests.utils.quote(symbol)}")
        if not isinstance(j, dict):
            return None
        pi = j.get("priceInfo") or {}
        o, c = num(pi.get("open")), num(pi.get("close")) or num(pi.get("lastPrice"))
        return {"open": o, "close": c} if o else None


def nse_match(issues, name):
    k = slugify(name)
    for x in issues:
        n = slugify(x.get("companyName") or x.get("company") or "")
        if n and (n == k or n.startswith(k) or k.startswith(n) or k.split("-")[:2] == n.split("-")[:2]):
            return x
    return None


# ---------------------------------------------------------------- merge
def apply_detail(ipo, d):
    for k in ("band", "lot", "issueCr", "freshCr", "registrar", "pe", "eps", "nav", "ronw", "roce", "de",
              "ebitdaM", "patM", "mcapCr"):
        if d.get(k) is not None:
            ipo[k] = d[k]
    if d.get("issueCr") is not None and d.get("freshCr") is not None:
        ipo["ofsCr"] = round(max(0.0, d["issueCr"] - d["freshCr"]), 2)
    if d.get("dates"):
        ipo.setdefault("dates", {}).update(d["dates"])
    if d.get("peers") and not ipo.get("peers"):
        ipo["peers"] = d["peers"]
    if d.get("fin"):                       # fill gaps year by year, never overwrite known values
        rows = {r["y"]: r for r in ipo.get("fin") or []}
        for r in d["fin"]:
            cur = rows.setdefault(r["y"], {"y": r["y"]})
            for k, v in r.items():
                if cur.get(k) is None and v is not None:
                    cur[k] = v
        ipo["fin"] = sorted(rows.values(), key=lambda r: (0 if r["y"].startswith("FY") else 1, r["y"]))
    if d.get("sub"):
        old = ipo.get("sub") or {}
        s = {**{k: old.get(k) for k in ("emp", "sh")}, **d["sub"]}
        s["asOf"] = TODAY.isoformat()
        close = (ipo.get("dates") or {}).get("close")
        s["final"] = bool(close and TODAY.isoformat() > close)
        days = [x for x in old.get("days", []) if x.get("d") != s["asOf"]]
        days.append({"d": s["asOf"], **{k: s.get(k) for k in ("total", "qib", "nii", "rii")}})
        s["days"] = sorted(days, key=lambda x: x["d"])[-10:]
        ipo["sub"] = s
    if d.get("gmp"):
        merge_gmp(ipo, d["gmp"])
    if d.get("url") and d["url"] not in ipo.setdefault("sources", []):
        ipo["sources"].append(d["url"])
    if ipo.get("band") and ipo.get("lot") and not ipo.get("minShares"):
        ipo["minShares"] = ipo["lot"] * (2 if ipo["lot"] * ipo["band"][1] < 200000 and ipo.get("seg") == "SME" else 1)
    ipo.pop("tentative", None) if ipo.get("dates", {}).get("open") and d.get("band") else None


def merge_gmp(ipo, pts):
    g = {p["d"]: p for p in ipo.get("gmp", [])}
    for p in pts:
        if p["d"] <= TODAY.isoformat():
            g[p["d"]] = {"d": p["d"], "v": p["v"]}
    lst = (ipo.get("dates") or {}).get("list")
    ipo["gmp"] = sorted((p for p in g.values() if not lst or p["d"] <= lst), key=lambda p: p["d"])[-30:]


def new_ipo(d, seg_hint):
    name = d.get("name") or d["slug"].replace("-", " ").title()
    return {"id": slugify(name)[:40], "gp": d["slug"], "name": name, "seg": seg_hint or d.get("seg") or "Mainboard",
            "exch": "NSE SME" if (seg_hint or d.get("seg")) == "SME" else "BSE, NSE", "sector": "",
            "band": [0, 0], "lot": None, "minShares": None, "fv": None, "issueCr": None, "freshCr": None,
            "ofsCr": None, "dates": {}, "fin": [], "peers": [], "sub": None, "gmp": [], "strengths": [],
            "risks": [], "objects": [], "views": [], "sources": [], "about": "",
            "finNote": "Figures collected automatically from public IPO pages; check the RHP."}


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    ipos = data["ipos"]
    by_gp = {i.get("gp") or i["id"]: i for i in ipos}

    disc = gp_discover()
    nse = NSE()
    issues = nse.issues()
    iw = ipowatch_gmp()

    # 1. refresh existing IPOs, then consider newly discovered ones
    for slug, ipo in list(by_gp.items()):
        d = gp_detail(slug)
        if d:
            apply_detail(ipo, d)
            log(f"updated {ipo['name']}")
    for slug, info in disc.items():
        if slug in by_gp or info.get("status") == "Listed":
            continue
        d = gp_detail(slug)
        if not d or not d.get("band") or not d.get("dates", {}).get("open"):
            continue
        dates = d["dates"]
        recent = dates.get("close") and dt.date.fromisoformat(dates["close"]) >= TODAY - dt.timedelta(days=4)
        soon = dt.date.fromisoformat(dates["open"]) <= TODAY + dt.timedelta(days=10)
        if not (recent and soon):
            continue
        ipo = new_ipo(d, info.get("seg"))
        apply_detail(ipo, d)
        if ipo["id"] in {i["id"] for i in ipos}:
            ipo["id"] += "-" + slug[:6]
        ipos.append(ipo); by_gp[slug] = ipo
        log(f"added {ipo['name']}")

    # 2. NSE overall subscription + today's GMP fallback + listing day
    listed = data["listed"]
    for ipo in ipos:
        x = nse_match(issues, ipo["name"])
        if x:
            ipo["nseSymbol"] = x.get("symbol") or ipo.get("nseSymbol")
            t = num(x.get("noOfTime") or x.get("noOfTimes"))
            if t is not None and (ipo.get("sub") or {}).get("asOf") != TODAY.isoformat():
                s = ipo.get("sub") or {"days": []}
                s.update(total=t, asOf=TODAY.isoformat(), final=False)
                ipo["sub"] = s
        q = iw.get(slugify(ipo["name"]))
        if q is not None and not any(p["d"] == TODAY.isoformat() for p in ipo.get("gmp", [])):
            merge_gmp(ipo, [{"d": TODAY.isoformat(), "v": q}])
        lst = (ipo.get("dates") or {}).get("list")
        if lst and TODAY.isoformat() >= lst and not (ipo.get("listing") or {}).get("open"):
            res = nse.listing(ipo["nseSymbol"]) if ipo.get("nseSymbol") else None
            if not res:
                d = gp_detail(ipo.get("gp") or ipo["id"]) or {}
                res = {"open": d["listOpen"], "close": None} if d.get("listOpen") else None
            if res:
                ipo["listing"] = res
                issue = ipo.get("issuePrice") or ipo["band"][1]
                ret = round(((res.get("close") or res["open"]) - issue) / issue * 100, 2)
                listed[:] = [r for r in listed if slugify(r[0]) != slugify(ipo["name"])]
                listed.insert(0, [ipo["name"], "S" if ipo["seg"] == "SME" else "M", lst, issue, res["open"],
                                  (ipo.get("sub") or {}).get("total") or 0, ret])
                log(f"listing recorded {ipo['name']}: {res}")

    # 3. housekeeping
    keep = []
    for ipo in ipos:
        lst = (ipo.get("dates") or {}).get("list")
        if lst and dt.date.fromisoformat(lst) < TODAY - dt.timedelta(days=3) and (ipo.get("listing") or {}).get("open"):
            continue
        if not lst and (ipo.get("dates") or {}).get("close") and \
                dt.date.fromisoformat(ipo["dates"]["close"]) < TODAY - dt.timedelta(days=21):
            continue
        keep.append(ipo)
    data["ipos"] = keep
    cutoff = (TODAY - dt.timedelta(days=90)).isoformat()
    data["listed"] = sorted([r for r in listed if r[2] >= cutoff], key=lambda r: r[2], reverse=True)

    if not ok_sources:
        log("No source reachable: data left unchanged.")
        return 1
    data["asOf"] = NOW.strftime("%d %b %Y, %H:%M IST").lstrip("0")
    data["version"] = NOW.strftime("%Y-%m-%d-%H%M")
    data["sources"] = sorted(ok_sources)
    DATA.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"saved: {len(data['ipos'])} IPOs, {len(data['listed'])} listings, sources {sorted(ok_sources)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
