"""Screenshot each site in portfolio/sites.json, run Lighthouse on it, and
rewrite the README section between the PORTFOLIO markers."""
import json, pathlib, re, subprocess, sys
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

def lighthouse(site):
    """Median of three mobile runs per category, since single runs are noisy."""
    runs = []
    for _ in range(3):
        out = subprocess.run(
            ["npx", "--yes", "lighthouse@12", site["url"], "--output=json", "--quiet",
             "--only-categories=" + ",".join(c for c, _ in CATEGORIES),
             "--chrome-flags=--headless=new --no-sandbox"],
            check=True, capture_output=True, text=True, timeout=300).stdout
        cats = json.loads(out)["categories"]
        runs.append({c: round(cats[c]["score"] * 100) for c, _ in CATEGORIES})
    return {c: sorted(r[c] for r in runs)[1] for c, _ in CATEGORIES}

def badge(label, score):
    color = "0cce6b" if score >= 90 else "ffa400" if score >= 50 else "ff4e42"
    return (f'<img src="https://img.shields.io/badge/{label.replace(" ", "%20")}-{score}-{color}'
            f'?style=flat-square" alt="{label} {score}" />')

def cell(site, scores):
    badges = "\n      ".join(badge(label, scores[c]) for c, label in CATEGORIES)
    return f"""    <td width="50%" valign="top">
      <a href="{site['url']}"><img src="portfolio/{site['slug']}.jpg" alt="{site['name']} homepage" /></a>
      <br /><b><a href="{site['url']}">{site['name']}</a></b>
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
               "\n</table>\n\n<sub>Lighthouse scores are mobile, median of three runs, refreshed weekly.</sub>\n<!-- PORTFOLIO:END -->")
    readme = ROOT / "README.md"
    text = re.sub(r"<!-- PORTFOLIO:START -->.*<!-- PORTFOLIO:END -->", lambda _: section,
                  readme.read_text(), flags=re.S)
    readme.write_text(text)

main()
