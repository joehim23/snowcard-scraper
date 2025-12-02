#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import time
import urllib.parse
from datetime import datetime, timedelta

BASE_URL = "https://www.snowcard.tirol.at/skigebiete"
OUTPUT_HTML = "skigebiete_snowcard.html"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_html(url):
    resp = requests.get(url, headers=HEADERS, timeout=20, verify=False)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text

def parse_overview_page(html):
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for item in soup.select("div.skigebiete_list_item"):
        name_tag = item.find("h5")
        if not name_tag:
            continue
        name = name_tag.get_text(strip=True)

        website = ""
        info_link = ""

        for a in item.select("div.links a"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if "Website" in text and href:
                website = href
            elif "Infos" in text and href:
                info_link = urllib.parse.urljoin(BASE_URL, href)

        if name and info_link:
            entries.append((name, website, info_link))
    return entries

def parse_detail_page(url):
    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        def extract_data(label):
            box = soup.find("h6", string=label)
            if not box:
                return []
            parent = box.find_parent("div", class_="location_weatherdata_item")
            return [v.get_text(strip=True) for v in parent.find_all("strong")]

        t = extract_data("Temperatur")
        s = extract_data("Schneehöhe")
        snow_min, snow_max = (s + ["", ""])[:2]
        temp_min, temp_max = (t + ["", ""])[:2]

        last_snow = ""
        ls = soup.find("h6", string="Letzter Schneefall")
        if ls:
            parent = ls.find_parent("div", class_="location_weatherdata_item")
            strong = parent.find("strong")
            if strong:
                last_snow = strong.get_text(strip=True)

        status = ""
        return {
            "Skigebiet": "",
            "Webseite": "",
            "Snowcard": url,
            "Schnee_min": snow_min,
            "Schnee_max": snow_max,
            "Temp_min": temp_min,
            "Temp_max": temp_max,
            "Letzter_Schneefall": last_snow,
            "Status": status
        }
    except Exception as e:
        print(f"Fehler bei {url}: {e}")
        return {
            "Skigebiet": "",
            "Webseite": "",
            "Snowcard": url,
            "Schnee_min": "",
            "Schnee_max": "",
            "Temp_min": "",
            "Temp_max": "",
            "Letzter_Schneefall": "",
            "Status": ""
        }

def parse_number_to_zero(text):
    """Parse Zahl; wenn leer/ungültig -> 0 (Benutzerwunsch)."""
    if not text:
        return 0.0
    t = text.replace("cm","").replace("°C","").replace("°","").replace("–","").strip()
    t = t.replace(",", ".")
    filtered = "".join(ch for ch in t if ch.isdigit() or ch in "-.")
    if filtered in ("", "-", "."):
        return 0.0
    try:
        return float(filtered)
    except:
        return 0.0

def parse_de_date_to_iso_and_epoch_default(text):
    """
    Parse German date. Wenn fehlt oder ungültig: Rückgabe '1970-01-01' und epoch 0.
    Sonst (ISO, epoch).
    """
    if not text:
        return "1970-01-01", 0
    raw = text.strip()
    if raw in ("–", "-", ""):
        return "1970-01-01", 0
    raw = raw.replace("/", ".").replace("-", ".")
    parts = [p.strip() for p in raw.split(".") if p.strip() != ""]
    if len(parts) < 3:
        return "1970-01-01", 0
    d_str, m_str, y_str = parts[0:3]
    try:
        d = int(d_str)
        m = int(m_str)
        y = int(y_str)
        if y < 100:
            y += 2000
        dt = datetime(year=y, month=m, day=d)
        iso = dt.strftime("%Y-%m-%d")
        epoch = int(dt.timestamp())
        return iso, epoch
    except Exception:
        return "1970-01-01", 0

def escape_html(s):
    if s is None:
        return ""
    return (str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            .replace('"',"&quot;").replace("'", "&#39;"))

def short_domain(url):
    if not url:
        return ""
    try:
        p = urllib.parse.urlparse(url if "://" in url else "http://" + url)
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except:
        return url

def generate_html(results):
    html = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Snowcard Tirol — Übersicht</title>
<style>
body{font-family:Arial,Segoe UI,Helvetica,sans-serif;background:#1b1f24;color:#e0e6ed;margin:18px}
h1{color:#4fc3f7}
table{width:100%;border-collapse:collapse;background:#2a2f36}
thead{background:#37414b;color:#fff}
th,td{padding:8px;border-bottom:1px solid #444b55;text-align:left;white-space:nowrap}
th{cursor:pointer}
tr:hover td{background:#333941}
.fresh{background:#004d40;color:#fff;font-weight:700}
a{color:#4fc3f7}
.controls{display:flex;gap:10px;align-items:center;margin-bottom:8px}
#search{padding:6px;width:300px;border-radius:6px;border:1px solid #444b55;background:#23272b;color:#e0e6ed}
.small{font-size:12px;color:#9aa4af}
</style>
</head>
<body>
<h1>Snowcard Tirol — Übersicht</h1>
<div class="controls"><input id="search" placeholder="Skigebiet suchen..." /><label><input id="filterOpen" type="checkbox" /> nur offene Gebiete</label><div class="small">Klicken sortiert (Toggle auf/ab). Standard: Letzter Schneefall ↓</div></div>
<table id="table"><thead><tr><th>Skigebiet</th><th>Webseite</th><th>Snowcard-Link</th><th>Schnee min (cm)</th><th>Schnee max (cm)</th><th>Temp min (°C)</th><th>Temp max (°C)</th><th data-type="date">Letzter Schneefall</th><th>Offen</th></tr></thead><tbody>
"""
    for r in results:
        skiname = escape_html(r.get("Skigebiet",""))
        web = r.get("Webseite","") or ""
        snowlink = r.get("Snowcard","") or ""
        smin = r.get("Schnee_min","") or ""
        smax = r.get("Schnee_max","") or ""
        tmin = r.get("Temp_min","") or ""
        tmax = r.get("Temp_max","") or ""
        last_raw = r.get("Letzter_Schneefall","") or ""
        status = escape_html(r.get("Status","") or "")

        # compute sort-values and defaults BEFORE escaping/display
        smin_sort = parse_number_to_zero(smin)        # 0.0 if missing
        smax_sort = parse_number_to_zero(smax)
        tmin_sort = parse_number_to_zero(tmin)
        tmax_sort = parse_number_to_zero(tmax)
        last_iso, last_epoch = parse_de_date_to_iso_and_epoch_default(last_raw)  # iso or '1970-01-01' and epoch int

        # display replacements per user request: missing snow -> "0 cm", missing date -> "1970-01-01"
        smin_show = escape_html(smin if smin.strip() else "0 cm")
        smax_show = escape_html(smax if smax.strip() else "0 cm")
        tmin_show = escape_html(tmin if tmin.strip() else "0 °C")
        tmax_show = escape_html(tmax if tmax.strip() else "0 °C")
        last_show = escape_html(last_iso)  # will be '1970-01-01' if missing

        web_show = short_domain(web)
        fresh = False
        # consider fresh only if date not default epoch 0
        if last_epoch and last_epoch != 0:
            try:
                d = datetime.fromtimestamp(last_epoch)
                if datetime.now() - d <= timedelta(days=3):
                    fresh = True
            except:
                pass

        tr_class = "fresh" if fresh else ""
        web_html = f'<a href="{escape_html(web)}" target="_blank" rel="noopener">{escape_html(web_show)}</a>' if web else ""
        snow_html = f'<a href="{escape_html(snowlink)}" target="_blank" rel="noopener">Link</a>' if snowlink else ""

        # last_sort_attr numeric epoch (0 for missing)
        last_sort_attr = str(last_epoch if last_epoch is not None else 0)

        html += f'<tr class="{tr_class}">'
        html += f"<td>{skiname}</td>"
        html += f"<td>{web_html}</td>"
        html += f"<td>{snow_html}</td>"
        html += f'<td data-sort="{smin_sort}">{smin_show}</td>'
        html += f'<td data-sort="{smax_sort}">{smax_show}</td>'
        html += f'<td data-sort="{tmin_sort}">{tmin_show}</td>'
        html += f'<td data-sort="{tmax_sort}">{tmax_show}</td>'
        html += f'<td data-sort="{last_sort_attr}">{last_show}</td>'
        html += f"<td>{status}</td>"
        html += "</tr>\n"

    html += """
</tbody></table>
<script>
/* compare: numeric data-sort first (numbers include snow heights, temps, and date-epochs).
   Empty values already replaced by numeric defaults (0), so compare is straightforward.
   Default sort still places highest/most recent first when requested. */
function toNum(v){
  if(v===null||v===undefined||v==='') return null;
  const n = Number(String(v));
  return isNaN(n) ? null : n;
}

function compareCells(aCell, bCell){
  const aRaw = (aCell.dataset && aCell.dataset.sort !== undefined) ? String(aCell.dataset.sort).trim() : String(aCell.innerText || "").trim();
  const bRaw = (bCell.dataset && bCell.dataset.sort !== undefined) ? String(bCell.dataset.sort).trim() : String(bCell.innerText || "").trim();

  const aNum = toNum(aRaw);
  const bNum = toNum(bRaw);
  if(aNum !== null && bNum !== null) return aNum - bNum;

  return aRaw.localeCompare(bRaw, 'de', {numeric:true});
}

const table = document.getElementById('table');
let lastCol = null, asc = true;

function sortByColumn(idx, ascending){
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  rows.sort((r1, r2) => {
    const cmp = compareCells(r1.cells[idx], r2.cells[idx]);
    return ascending ? cmp : -cmp;
  });
  rows.forEach(r => tbody.appendChild(r));
  lastCol = idx;
  asc = ascending;
}

// attach click handlers (toggle)
Array.from(table.querySelectorAll('th')).forEach((th, idx) => {
  th.addEventListener('click', () => {
    const newAsc = (lastCol === idx) ? !asc : true;
    sortByColumn(idx, newAsc);
  });
});

// default sort by Letzter Schneefall (column index 7) descending (newest first)
document.addEventListener('DOMContentLoaded', () => {
  sortByColumn(7, false);
});

// search
document.getElementById('search').addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase();
  Array.from(table.querySelectorAll('tbody tr')).forEach(tr => {
    tr.style.display = tr.cells[0].innerText.toLowerCase().includes(q) ? '' : 'none';
  });
});

// filter open
document.getElementById('filterOpen').addEventListener('change', (e) => {
  const on = e.target.checked;
  const q = document.getElementById('search').value.toLowerCase();
  Array.from(table.querySelectorAll('tbody tr')).forEach(tr => {
    const okOpen = !on || tr.cells[8].innerText.toLowerCase().includes('offen');
    const okSearch = !q || tr.cells[0].innerText.toLowerCase().includes(q);
    tr.style.display = (okOpen && okSearch) ? '' : 'none';
  });
});
</script>
</body>
</html>
"""
    return html

def main():
    all_entries = []
    for ch in [chr(c) for c in range(ord("a"), ord("z")+1)]:
        page = 1
        while True:
            url = f"{BASE_URL}/{ch}?page={page}" if page > 1 else f"{BASE_URL}/{ch}"
            html = fetch_html(url)
            soup = BeautifulSoup(html, "html.parser")
            if "Leider nichts gefunden" in soup.get_text():
                break
            entries = parse_overview_page(html)
            if not entries:
                break
            all_entries.extend(entries)
            print(f"[{ch.upper()} Seite {page}] {len(entries)} Einträge")
            page += 1
            time.sleep(0.25)

    print(f"Gesamt: {len(all_entries)} Skigebiete. Lade Details...")
    results = []
    for name, website, info_link in all_entries:
        detail = parse_detail_page(info_link)
        detail["Webseite"] = website
        detail["Skigebiet"] = name
        results.append(detail)
        print(f"{name}: {detail.get('Letzter_Schneefall','')}")
        time.sleep(0.25)

    html = generate_html(results)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML gespeichert:", OUTPUT_HTML)

if __name__ == "__main__":
    main()
