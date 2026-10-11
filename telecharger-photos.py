#!/usr/bin/env python3
"""Télécharge jusqu'à 4 photos par étape depuis Wikipédia dans photos/,
puis met à jour la liste des photos lue par index.html (data/photos.js).

Usage :
  python3 telecharger-photos.py           télécharge ce qui manque
  python3 telecharger-photos.py --force   retélécharge tout

Tes propres photos : dépose-les dans photos/ en les nommant avec le numéro
de l'étape devant, par exemple 05-moi.jpg, puis relance le script.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PHOTOS = ROOT / "photos"
MAX = 4
UA = {"User-Agent": "road-trip-usa-photos/2.0 (usage personnel)"}
API = "https://en.wikipedia.org/api/rest_v1/page/"
SKIP = re.compile(r"map|carte|locator|location|logo|seal|flag|diagram|icon|symbol|sign|chart|plan|svg|coat_of_arms|wikisource|commons-logo", re.I)
EXT = (".jpg", ".jpeg", ".png", ".webp")


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def page(title, kind):
    t = urllib.parse.quote(title.replace(" ", "_"), safe="")
    return json.loads(get(API + kind + "/" + t))


def candidates(titles):
    leads, extras = [], []
    for title in titles:
        try:
            s = page(title, "summary")
            img = s.get("originalimage") or s.get("thumbnail")
            if img:
                src = img["source"]
                if s.get("thumbnail") and img.get("width", 0) > 1400:
                    src = re.sub(r"/\d+px-", "/1280px-", s["thumbnail"]["source"])
                leads.append(src)
        except Exception as err:
            print(f"   - page « {title} » introuvable ({err})")
        try:
            for it in page(title, "media-list").get("items", []):
                name = it.get("title", "")
                if it.get("type") != "image" or not it.get("showInGallery", True):
                    continue
                if not name.lower().endswith((".jpg", ".jpeg")) or SKIP.search(name):
                    continue
                srcset = it.get("srcset") or []
                if srcset:
                    src = srcset[-1]["src"]
                    extras.append("https:" + src if src.startswith("//") else src)
        except Exception:
            pass
        time.sleep(0.3)
    seen, out = set(), []
    for src in leads + extras:
        key = re.sub(r"/\d+px-", "/", src).split("/")[-1]
        if key in seen or SKIP.search(key):
            continue
        seen.add(key)
        out.append(src)
    return out


def existing(n):
    return sorted(p for p in PHOTOS.iterdir() if p.suffix.lower() in EXT and re.match(rf"{n:02d}(-|\.)", p.name))


def main():
    force = "--force" in sys.argv
    raw = (ROOT / "data" / "etapes.js").read_text(encoding="utf-8")
    etapes = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
    PHOTOS.mkdir(exist_ok=True)
    for n, e in enumerate(etapes, start=1):
        if force:
            for p in PHOTOS.glob(f"{n:02d}-wiki*"):
                p.unlink()
        if existing(n) and not force:
            print(f"{n:02d} {e['nom']} : déjà {len(existing(n))} photo(s)")
            continue
        print(f"{n:02d} {e['nom']}")
        got = 0
        for src in candidates(e["wiki"]):
            if got >= MAX:
                break
            ext = Path(urllib.parse.urlparse(src).path).suffix.lower()
            ext = ext if ext in EXT else ".jpg"
            try:
                (PHOTOS / f"{n:02d}-wiki{got + 1}{ext}").write_bytes(get(src))
                got += 1
            except Exception as err:
                print(f"   - échec d'une image ({err})")
            time.sleep(0.3)
        print(f"   {got} photo(s)")
    manifest = {str(n): ["photos/" + p.name for p in existing(n)] for n in range(1, len(etapes) + 1)}
    (ROOT / "data" / "photos.js").write_text("window.PHOTOS = " + json.dumps(manifest, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    total = sum(len(v) for v in manifest.values())
    print(f"\n{total} photos au total. Ouvre index.html pour les voir.")


if __name__ == "__main__":
    main()
