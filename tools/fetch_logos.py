"""Download company logos from official websites (run on GitHub Actions)."""
import json, re, sys, pathlib, requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
OUT = pathlib.Path("logos"); OUT.mkdir(exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
SITES = {
 "crystal-crop": ["https://www.crystalcropprotection.com/"],
 "mahanadi-coalfields": ["https://www.mahanadicoal.in/", "https://mahanadicoal.in/", "https://www.coalindia.in/"],
 "watrana-rentals": ["https://www.watrana.com/", "https://watrana.com/", "https://www.watranarentals.com/", "https://www.watranatraction.com/"],
 "shree-siddhivinayak": ["https://www.shreesiddhivinayakgreentech.com/", "https://shreesiddhivinayakgreentech.com/", "https://www.ssgil.in/", "https://www.siddhivinayakgreentech.com/"],
 "foodlink-fb": ["https://www.foodlink.in/", "https://foodlink.in/"],
 "integris-medtech": ["https://www.integrismedtech.com/", "https://integrismedtech.com/"],
 "a-j-packaging": ["https://www.ajpack.net/", "http://www.ajpack.net/"],
 "matangi-rubber": ["https://www.matangirubber.com/", "https://matangirubber.com/", "https://www.matangirubber.in/", "https://www.matangirubbers.com/"],
 "monomark-engineering": ["https://www.monomark.co.in/", "http://www.monomark.co.in/"],
}
report = {}
def save(cid, tag, url):
    try:
        r = requests.get(url, headers=UA, timeout=20)
        if r.status_code != 200 or len(r.content) < 200: return None
        ct = r.headers.get("content-type", "")
        ext = "svg" if ("svg" in ct or url.lower().split("?")[0].endswith(".svg")) else ("ico" if "icon" in ct or url.lower().endswith(".ico") else ("jpg" if "jpeg" in ct else ("webp" if "webp" in ct else "png")))
        p = OUT / f"{cid}-{tag}.{ext}"; p.write_bytes(r.content); return str(p)
    except Exception as e:
        return None
for cid, urls in SITES.items():
    got = []
    for home in urls:
        try:
            r = requests.get(home, headers=UA, timeout=20, allow_redirects=True)
        except Exception as e:
            continue
        if r.status_code != 200: continue
        base = r.url; soup = BeautifulSoup(r.text, "html.parser")
        cands = []
        for img in soup.find_all("img"):
            s = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
            blob = " ".join([s, img.get("alt", ""), " ".join(img.get("class", []) or []), img.get("id", "") or ""]).lower()
            if "logo" in blob and s and not s.startswith("data:"): cands.append(("img", urljoin(base, s)))
        for ln in soup.find_all("link"):
            rel = " ".join(ln.get("rel", [])).lower()
            if "apple-touch-icon" in rel or "icon" in rel:
                if ln.get("href"): cands.append(("icon", urljoin(base, ln["href"])))
        cands.append(("fav", urljoin(base, "/favicon.ico")))
        dom = re.sub(r"^https?://", "", base).split("/")[0]
        cands.append(("g", f"https://www.google.com/s2/favicons?domain={dom}&sz=256"))
        seen = set(); n = 0
        for kind, u in cands:
            if u in seen or n >= 6: continue
            seen.add(u); f = save(cid, f"{kind}{n}", u)
            if f: got.append({"file": f, "url": u}); n += 1
        report[cid] = {"site": base, "files": got}; break
    else:
        report.setdefault(cid, {"site": None, "files": []})
(OUT / "report.json").write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1))
