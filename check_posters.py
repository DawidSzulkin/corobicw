import json
import re
import requests
import urllib3

urllib3.disable_warnings()

headers = {"User-Agent": "Mozilla/5.0", "RSC": "1"}
slug = "sasiedzi-z-gory"

# 1. Sprawdzenie endpointów API spektaklu
for ep in [f"/api/shows/{slug}", f"/api/shows", f"/api/show?slug={slug}", f"/spektakl/{slug}"]:
    r = requests.get(f"https://teatr.bielsko.pl{ep}", headers=headers, verify=False, timeout=8)
    imgs = re.findall(r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)', r.text, re.IGNORECASE)
    rel_imgs = re.findall(r'["\'](/uploads/[^"\']+|/media/[^"\']+|/_next/image\?url=[^"\']+)["\']', r.text)
    print(f"Endpoint {ep} -> Status: {r.status_code} | Obrazki: {len(imgs) + len(rel_imgs)}")
    if imgs or rel_imgs:
        print("  Przykłady:", (imgs + rel_imgs)[:3])