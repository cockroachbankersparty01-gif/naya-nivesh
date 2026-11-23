# Naya Nivesh – IPO & Allotment (standalone Android app)

A self-contained Android app. No website, no server, no Claude.

- **Live data inside the app:** every time you open it (and every 20 minutes while open,
  or when you tap **↻ Refresh**), the app downloads the latest public IPO pages straight
  to your phone: new mainboard and SME IPOs, daily GMP, category-wise subscription, dates,
  ratios, peers, financials and listing-day prices. It saves them on the phone, so the
  GMP history keeps building until listing and the app still works offline.
- **Analysis:** fundamentals, peer valuation, GMP ledger, subscription, scores and an
  apply / avoid call for each IPO; listing-day gain/loss tracker.
- **Allotment:** one-tap registrar / BSE / NSE status links and a private log of your
  applications (stored only on your phone).

## Getting the APK
This repository only builds the app. It can stay **private**.

1. Open the **Actions** tab → **Build Android APK** → **Run workflow** (it also runs
   automatically whenever the `android/` folder changes).
2. Wait for the green tick (about 5 minutes), open the run, and download
   **naya-nivesh-apk** under *Artifacts*.
3. Unzip on your phone, tap `app-debug.apk`, allow "Install unknown apps", install.

To update the app later, install the newer APK over the old one; your saved data stays.

## Data sources
Public pages from gmpipowatch.in (main source) and ipowatch.in (GMP fallback). If a site
is unreachable or changes its layout, the app keeps the last saved data and shows
"showing saved data". GMP is unofficial and unregulated. Not investment advice.

The app's code lives in `android/app/src/main/assets/index.html` (the whole app UI and
analysis) and `android/app/src/main/java/.../MainActivity.java` (the Android shell and
page downloader).
