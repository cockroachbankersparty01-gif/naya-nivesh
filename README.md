# Naya Nivesh – IPO & Allotment (self-updating)

Everything runs on free GitHub services. No Claude, no server, no paid API.

| Part | What it does | Where |
|---|---|---|
| Website | The full app (analysis, GMP ledger, listings, allotment checker) | `docs/` served by GitHub Pages |
| Data updater | Every 2 hours (8:47 am–8:47 pm IST) collects new IPOs, daily GMP, subscription, dates, KPIs, peers and listing-day prices, then saves `docs/data.json` | `scraper/update.py` + `.github/workflows/update-data.yml` |
| Android app | Opens instantly with bundled data, then downloads the latest `data.json` every time you open it | `android/` + `.github/workflows/build-apk.yml` |

## One-time setup (about 10 minutes, phone or computer)

1. **Create a GitHub account** (free) at github.com if you don't have one.
2. **New repository** → name it e.g. `naya-nivesh` → **Public** → Create.
   (Public is needed for free GitHub Pages and unlimited free Actions minutes.)
3. **Upload files**: on the repository page tap *Add file → Upload files*, and upload the
   **contents** of this folder (`docs`, `scraper`, `android`, `.github`, `README.md`).
   Tip: on a phone, the hidden `.github` folder may not upload; if so, create the two
   workflow files manually with *Add file → Create new file*, typing the path
   `.github/workflows/update-data.yml` and pasting the contents (same for `build-apk.yml`).
4. **Turn on the website**: *Settings → Pages → Build and deployment → Source: Deploy from a branch →
   Branch: `main`, folder: `/docs` → Save*. After a minute your app is live at
   `https://YOUR-USERNAME.github.io/naya-nivesh/`.
5. **Allow the updater to save data**: *Settings → Actions → General → Workflow permissions →
   Read and write permissions → Save*.
6. **Run it once now**: *Actions → Update IPO data → Run workflow*. From then on it runs by itself.
7. **Get the APK**: *Actions → Build Android APK → Run workflow*. When it finishes, open the run,
   download **naya-nivesh-apk**, unzip, install `app-debug.apk` on your phone
   (allow "Install unknown apps"). The APK is automatically wired to your repository's live data.

## Day to day
Nothing to do. Open the website or the app; the header shows the last refresh time.
If a data source is down or changes its layout, that run keeps the previous values and
GitHub emails you that the run failed; the next run tries again.

## Good to know
- Data sources: gmpipowatch.in IPO pages (GMP history, subscription, KPIs, peers, dates),
  ipowatch.in GMP table (fallback), NSE public endpoints (subscription, listing prices).
  These are public pages; check each site's terms. If NSE blocks GitHub's servers, the other
  sources still update.
- Automatically discovered IPOs get the numbers those pages publish (price band, KPIs, peers,
  financials). Strengths/risks are not written automatically; the app's red-flag checks and
  scores still run on the numbers.
- GitHub pauses scheduled workflows in a repository with no activity for 60 days. The
  updater's own commits normally count as activity; if it ever pauses, click *Enable workflow*
  in the Actions tab.
- GMP is unofficial and unregulated. Not investment advice.
