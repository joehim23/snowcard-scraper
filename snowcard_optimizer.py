#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import time
import urllib.parse
from datetime import datetime

BASE_URL = "https://www.snowcard.tirol.at/skigebiete"
OUTPUT_HTML = "skigebiete_snowcard.html"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_html(url):
    resp = requests.get(url, headers=HEADERS)
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
        status_box = soup.find("div", class_="status")  # falls Status verfügbar
        if status_box:
            status = status_box.get_text(strip=True)

        return {
            "Skigebiet": url.split("/")[-1],
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

def parse_number(text):
    if not text:
        return None
    t = text.replace("cm","").replace("°C","").replace("°","").replace("–","").strip()
    t = t.replace(",", ".")
    try:
        return float(t)
    except:
        return None

def parse_de_date_to_iso(text):
    if not text or text.strip() in ("–", "-", ""):
        return ""
    try:
        dt = datetime.strptime(text.strip(), "%d.%m.%Y")
        return dt.strftime("%Y-%m-%d")
    except:
        return text

def generate_html(results):
    html = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Snowcard Tirol Skigebiete</title>
<style>
body { font-family: Arial, sans-serif; background:#1b1f24; color:#e0e6ed; margin:20px; }
h1 { color:#4fc3f7; }
table { width:100%; border-collapse:collapse; margin-top:15px; background:#2a2f36; }
thead { background:#37414b; color:#ffffff; }
th, td { padding:10px; border-bottom:1px solid #444b55; text-align:left; }
th { cursor:pointer; }
tr:hover { background:#333941; }
.fresh-snow { background:#004d40; color:#fff; font-weight:bold; }
a { color:#4fc3f7; text-decoration:none; }
a:hover { text-decoration:underline; }
#searchInput { padding:8px; width:280px; margin-right:20px; border-radius:5px; border:1px solid #444b55; background:#2a2f36; color:#e0e6ed; }
</style>
</head>
<body>

<h1>Snowcard Tirol – Überblick</h1>
<input type="text" id="searchInput" placeholder="Skigebiet suchen …">
<label><input type="checkbox" id="filterOpen"> nur offene Gebiete</label>

<table id="skiTable">
<thead>
<tr>
<th>Skigebiet</th>
<th>Webseite</th>
<th>Snowcard-Link</th>
<th>Schnee min (cm)</th>
<th>Schnee max (cm)</th>
<th>Temp min (°C)</th>
<th>Temp max (°C)</th>
<th data-type="date">Letzter Schneefall</th>
<th>Offen</th>
</tr>
</thead>
<tbody>
"""
    for r in results:
        # Daten für Sortierung vorbereiten
        snow_min_sort = parse_number(r["Schnee_min"])
        snow_max_sort = parse_number(r["Schnee_max"])
        temp_min_sort = parse_number(r["Temp_min"])
        temp_max_sort = parse_number(r["Temp_max"])
        last_snow_iso = parse_de_date_to_iso(r["Letzter_Schneefall"])

        fresh = False
        try:
            dt = datetime.strptime(r["Letzter_Schneefall"], "%d.%m.%Y")
            if (datetime.now() - dt).days <= 3:
                fresh = True
        except:
            pass

        row_class = "fresh-snow" if fresh else ""

        html += f'<tr class="{row_class}">'
        html += f'<td>{r["Skigebiet"]}</td>'
        html += f'<td><a href="{r.get("Webseite","")}" target="_blank">{r.get("Webseite","")}</a></td>'
        html += f'<td><a href="{r.get("Snowcard","")}" target="_blank">Link</a></td>'
        html += f'<td data-sort="{snow_min_sort if snow_min_sort is not None else ""}">{r["Schnee_min"]}</td>'
        html += f'<td data-sort="{snow_max_sort if snow_max_sort is not None else ""}">{r["Schnee_max"]}</td>'
        html += f'<td data-sort="{temp_min_sort if temp_min_sort is not None else ""}">{r["Temp_min"]}</td>'
        html += f'<td data-sort="{temp_max_sort if temp_max_sort is not None else ""}">{r["Temp_max"]}</td>'
        html += f'<td data-sort="{last_snow_iso}">{r["Letzter_Schneefall"]}</td>'
        html += f'<td>{r["Status"]}</td>'
        html += "</tr>\n"

    html += """
</tbody>
</table>

<script>
// Sortierung
function tryNumber(s){ const n=parseFloat(s); return isNaN(n)?null:n; }
function compareCells(a,b){
    const aVal = a.dataset.sort || a.innerText;
    const bVal = b.dataset.sort || b.innerText;
    const aNum = tryNumber(aVal), bNum = tryNumber(bVal);
    if(aNum !== null && bNum !== null) return aNum-bNum;
    return aVal.localeCompare(bVal,'de',{numeric:true});
}

const table=document.getElementById('skiTable');
let sortCol=null, asc=true;
table.querySelectorAll('th').forEach((th,i)=>{
    th.addEventListener('click',()=>{
        asc=(sortCol===i)?!asc:true;
        sortCol=i;
        const tbody=table.tBodies[0];
        Array.from(tbody.rows)
            .sort((r1,r2)=>asc?compareCells(r1.cells[i],r2.cells[i]):compareCells(r2.cells[i],r1.cells[i]))
            .forEach(r=>tbody.appendChild(r));
    });
});

// Suche
document.getElementById("searchInput").addEventListener("input",()=>{
    const val=document.getElementById("searchInput").value.toLowerCase();
    table.querySelectorAll("tbody tr").forEach(r=>{
        r.style.display=r.cells[0].innerText.toLowerCase().includes(val)?"":"none";
    });
});

// Filter offene Gebiete
document.getElementById("filterOpen").addEventListener("change",()=>{
    const active=document.getElementById("filterOpen").checked;
    table.querySelectorAll("tbody tr").forEach(r=>{
        const status=r.cells[8].innerText.toLowerCase();
        r.style.display=(active && !status.includes("offen"))?"none":"";
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
            url = f"{BASE_URL}/{ch}?page={page}" if page>1 else f"{BASE_URL}/{ch}"
            html = fetch_html(url)
            soup = BeautifulSoup(html, "html.parser")
            if "Leider nichts gefunden" in soup.get_text():
                break
            entries = parse_overview_page(html)
            if not entries:
                break
            all_entries.extend(entries)
            print(f"[{ch.upper()} Seite {page}] {len(entries)} Einträge gefunden.")
            page+=1
            time.sleep(0.3)

    print(f"Insgesamt {len(all_entries)} Skigebiete gefunden. Lade Wetterdaten …")

    results = []
    for name, website, info_link in all_entries:
        detail = parse_detail_page(info_link)
        # Webseite setzen
        detail["Webseite"] = website
        detail["Skigebiet"] = name
        results.append(detail)
        print(f"{name}: {detail['Letzter_Schneefall']}")
        time.sleep(0.25)

    html = generate_html(results)
    with open(OUTPUT_HTML,"w",encoding="utf-8") as f:
        f.write(html)
    print(f"\nHTML gespeichert unter: {OUTPUT_HTML}")

if __name__=="__main__":
    main()