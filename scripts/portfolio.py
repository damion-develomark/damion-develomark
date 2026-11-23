"""Screenshot each site in portfolio/sites.json, run Lighthouse on it, and
rewrite the README section between the PORTFOLIO markers."""
import json, os, pathlib, re, sys, time, urllib.error, urllib.parse, urllib.request
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITES = json.loads((ROOT / "portfolio/sites.json").read_text())
CATEGORIES = [("performance", "Performance"), ("accessibility", "Accessibility"),
              ("best-practices", "Best Practices"), ("seo", "SEO")]

def screenshot(site):
    """Real-time wait (not virtual time) so intro animations finish first."""
    from playwright.sync_api import sync_playwright
    png = ROOT / f"portfolio/{site['slug']}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto(site["url"], wait_until="networkidle", timeout=60000)
        except Exception:
            page.goto(site["url"], wait_until="load", timeout=60000)
        page.wait_for_timeout(8000)
        page.screenshot(path=str(png))
        browser.close()
    img = Image.open(png).convert("RGB")
    img.thumbnail((960, 600))
    img.save(ROOT / f"portfolio/{site['slug']}.jpg", quality=82, optimize=True, progressive=True)
    png.unlink()

PSI = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
SKIP_MODES = {"notApplicable", "manual", "informative"}

def psi(url):
    """One mobile PageSpeed Insights run, retried on rate limits and server errors."""
    params = [("url", url), ("strategy", "mobile")] + [("category", c.upper().replace("-", "_")) for c, _ in CATEGORIES]
    if os.environ.get("PSI_API_KEY"):
        params.append(("key", os.environ["PSI_API_KEY"]))
    for attempt in range(5):
        try:
            with urllib.request.urlopen(PSI + "?" + urllib.parse.urlencode(params), timeout=120) as r:
                return json.load(r)["lighthouseResult"]
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500 or attempt == 4:
                raise SystemExit(f"PSI {e.code} for {url}: {e.read().decode()[:300]}")
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
        time.sleep(15 * (attempt + 1))

def seo_score(lhr, preview):
    """Lighthouse's weighted SEO mean. Preview deployments are noindexed on purpose,
    so they skip the is-crawlable audit; production sites are scored as-is."""
    num = den = 0
    for ref in lhr["categories"]["seo"]["auditRefs"]:
        audit = lhr["audits"][ref["id"]]
        if not ref["weight"] or audit["scoreDisplayMode"] in SKIP_MODES:
            continue
        if preview and ref["id"] == "is-crawlable":
            continue
        num += ref["weight"] * (audit["score"] or 0)
        den += ref["weight"]
    return round(num / den * 100)

def lighthouse(site):
    """Median of three mobile PageSpeed Insights runs per category, since single runs are noisy."""
    runs = []
    for _ in range(3):
        lhr = psi(site["url"])
        scores = {c: round(lhr["categories"][c]["score"] * 100) for c, _ in CATEGORIES}
        scores["seo"] = seo_score(lhr, site.get("preview", False))
        runs.append(scores)
    return {c: sorted(r[c] for r in runs)[1] for c, _ in CATEGORIES}

def badge(label, score):
    color = "0cce6b" if score >= 90 else "ffa400" if score >= 50 else "ff4e42"
    return (f'<img src="https://img.shields.io/badge/{label.replace(" ", "%20")}-{score}-{color}'
            f'?style=flat-square" alt="{label} {score}" />')

def cell(site, scores):
    badges = "\n      ".join(badge(label, scores[c]) for c, label in CATEGORIES)
    return f"""    <td width="50%" valign="top">
      <a href="{site['url']}"><img src="portfolio/{site['slug']}.jpg" alt="{site['name']} homepage" /></a>
      <br /><b><a href="{site['url']}">{site['name']}</a></b>{" †" if site.get("preview") else ""}
      <br /><sub>{site['blurb']}</sub>
      <br />
      {badges}
    </td>"""

def main():
    cells = []
    for site in SITES:
        print("::group::" + site["name"]); sys.stdout.flush()
        screenshot(site)
        scores = lighthouse(site)
        print(scores); print("::endgroup::")
        cells.append(cell(site, scores))
    rows = ["  <tr>\n" + "\n".join(cells[i:i + 2]) + "\n  </tr>" for i in range(0, len(cells), 2)]
    section = ("<!-- PORTFOLIO:START -->\n<table>\n" + "\n".join(rows) +
               "\n</table>\n\n<sub>Lighthouse scores are mobile via PageSpeed Insights, median of three runs, refreshed weekly. "
               "† Preview deployment, noindexed until launch, so SEO excludes the indexability check.</sub>\n<!-- PORTFOLIO:END -->")
    readme = ROOT / "README.md"
    text = re.sub(r"<!-- PORTFOLIO:START -->.*<!-- PORTFOLIO:END -->", lambda _: section,
                  readme.read_text(), flags=re.S)
    readme.write_text(text)

main()
