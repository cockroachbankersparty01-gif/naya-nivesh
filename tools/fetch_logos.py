"""Find and download company logos for every IPO in the app (live, upcoming, listed).
Sources, in order: the IPO's page on gmpipowatch.in, then the company's official website
(found through a DuckDuckGo search), then the site's icon. Runs on GitHub Actions."""
import json, re, time, pathlib, html as H
from urllib.parse import urljoin, urlparse, parse_qs, quote_plus, unquote
import requests
from bs4 import BeautifulSoup
OUT = pathlib.Path("logos/auto"); OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36", "Accept-Language": "en-IN,en;q=0.9"}
BLOCK = """chittorgarh ipowatch gmpipowatch investorgain ipoji ipocentral ipoplatform kotakneo zerodha groww angelone 5paisa moneycontrol economictimes livemint business-standard tofler zaubacorp indiamart tradeindia linkedin facebook instagram twitter x.com youtube wikipedia justdial crunchbase bseindia nseindia sebi screener trendlyne tickertape smartkarma cbinsights zoominfo glassdoor ambitionbox bajajbroking dhan.co upstox paytm indmoney hdfcsec icicidirect sharekhan motilaloswal samco ipogyani ipomarket chanakyanipothi alphave multibagg valueresearch goodreturns financialexpress ndtv indiatimes thehindubusinessline cnbctv18 news18 ipoguru iifl indiainfoline reddit quora instafinancials qorpiq companydetails emis dnb.com village.ai uplers leadiq craft.co tracxn pitchbook duckduckgo google bing yahoo amazon flipkart wikipedia.org scribd slideshare marketsmojo stockedge dsij ipodekho ipoalerts ipopremium ipoplanet nirmalbang choiceindia jmfinancial axisdirect equitymaster rediff""".split()
STOP = {"limited","ltd","india","industries","the","and","of","pvt","private","company","co","(india)","technologies","engineering","holdings","enterprises","group","solutions","services"}
def key(n): return re.sub(r"[^a-z0-9]", "", re.sub(r"\b(ltd|limited|ipo|sme)\b", "", n.lower()))
def tokens(n): return [t for t in re.findall(r"[a-z0-9]+", n.lower()) if len(t) >= 3 and t not in STOP]
def get(u, **k):
    try:
        r = requests.get(u, headers=UA, timeout=20, allow_redirects=True, **k)
        return r if r.status_code == 200 else None
    except Exception: return None
def save(k, src, url):
    r = get(url)
    if not r or len(r.content) < 300: return None
    ct = r.headers.get("content-type", "").lower()
    if "html" in ct: return None
    ext = "svg" if "svg" in ct or url.lower().split("?")[0].endswith(".svg") else "ico" if ("icon" in ct or url.lower().split("?")[0].endswith(".ico")) else "jpg" if "jpeg" in ct else "webp" if "webp" in ct else "png"
    p = OUT / f"{k}.{ext}"; p.write_bytes(r.content)
    return {"file": str(p), "url": url, "src": src}
def logo_from_page(base, soup, name):
    toks = tokens(name); best = []
    for img in soup.find_all("img"):
        s = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        if not s or s.startswith("data:"): continue
        blob = " ".join([s, img.get("alt", ""), " ".join(img.get("class", []) or []), img.get("id", "") or ""]).lower()
        score = (3 if "logo" in blob else 0) + sum(1 for t in toks if t in blob)
        if img.find_parent(["header", "nav"]): score += 1
        if score >= 3: best.append((score, urljoin(base, s)))
    best.sort(key=lambda x: -x[0])
    out = [u for _, u in best[:2]]
    for ln in soup.find_all("link"):
        rel = " ".join(ln.get("rel", [])).lower()
        if "apple-touch-icon" in rel and ln.get("href"): out.append(urljoin(base, ln["href"]))
    for ln in soup.find_all("link"):
        rel = " ".join(ln.get("rel", [])).lower()
        if "icon" in rel and ln.get("href"): out.append(urljoin(base, ln["href"]))
    return out
def find_site(name):
    q = quote_plus(f"{name} limited official website")
    toks = tokens(name); links = []
    r = get(f"https://www.bing.com/search?q={q}&setlang=en-IN")
    if r: links += [a.get("href", "") for a in BeautifulSoup(r.text, "html.parser").select("li.b_algo h2 a")]
    r = get(f"https://html.duckduckgo.com/html/?q={q}")
    if r: links += [a.get("href", "") for a in BeautifulSoup(r.text, "html.parser").select("a.result__a")]
    for href in links:
        if "uddg=" in href: href = unquote(parse_qs(urlparse(href if href.startswith("http") else "https:" + href).query).get("uddg", [""])[0])
        dom = urlparse(href).netloc.lower().replace("www.", "")
        if not dom or any(b in dom for b in BLOCK): continue
        if any(t[:5] in dom.replace("-", "") for t in toks): return f"https://{urlparse(href).netloc}/"
    return None
def gp_slug(name): return re.sub(r"[^a-z0-9]+", "-", re.sub(r"\b(ltd|limited)\b\.?", "", name.lower()).replace("&", "")).strip("-")
def main():
    src = pathlib.Path("android/app/src/main/assets/index.html").read_text(encoding="utf-8")
    seed = json.loads(re.search(r'<script id="seed" type="application/json">(.*?)</script>', src, re.S).group(1))
    names = [(i["name"], i.get("gp")) for i in seed["ipos"]] + [(r[0], None) for r in seed["listed"]]
    rep = {}
    prevf = OUT / "report.json"; prev = json.loads(prevf.read_text()) if prevf.exists() else {}
    for name, gp in names:
        k = key(name); hit = None; site = None
        # 0) skip if already found on an earlier run
        old = [f for f in OUT.glob(k + ".*")]
        if old and k in prev and prev[k].get("src"):
            rep[k] = prev[k]; continue
        # 1) IPO tracker: direct upload paths for common slug variants, then the IPO page
        sl = gp or gp_slug(name)
        for v in [sl, sl + "-ltd", sl + "-limited", sl.replace("-india", ""), sl.split("-")[0] + "-" + sl.split("-")[1] if sl.count("-") >= 1 else sl]:
            for ext in ("png", "jpg", "webp"):
                hit = save(k, "ipo-page", f"https://www.gmpipowatch.in/uploads/ipos/{v}.{ext}")
                if hit: break
            if hit: break
        r = None if hit else get(f"https://www.gmpipowatch.in/ipo/{sl}")
        if r:
            soup = BeautifulSoup(r.text, "html.parser")
            for u in logo_from_page(r.url, soup, name)[:2]:
                if "gmpipowatch" in u and "logo" in u.lower() and not any(t in u.lower() for t in tokens(name)): continue
                hit = save(k, "ipo-page", u)
                if hit: break
        # 2) official website
        if not hit:
            site = find_site(name); time.sleep(1.5)
            if site:
                r = get(site)
                if r:
                    for u in logo_from_page(r.url, BeautifulSoup(r.text, "html.parser"), name)[:4]:
                        hit = save(k, "website", u)
                        if hit: break
                if not hit:
                    hit = save(k, "favicon", f"https://www.google.com/s2/favicons?domain={urlparse(site).netloc}&sz=256")
        rep[k] = {"name": name, "site": site, **(hit or {})}
        print(name, "->", hit and hit["src"], hit and hit["url"][:90], flush=True)
    (OUT / "report.json").write_text(json.dumps(rep, indent=1))
main()
