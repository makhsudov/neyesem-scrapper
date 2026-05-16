import requests
import json

base = "https://food-client-api-gateway.getirapi.com"
lat, lon = 40.1885, 29.0610

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Origin": "https://getir.com",
    "Referer": "https://getir.com/",
}

r = requests.get(base + "/restaurants", params={"lat": lat, "lon": lon}, headers=headers, timeout=15)
print("Status:", r.status_code)
data = r.json()

with open("output/debug_direct_api.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("Saved to output/debug_direct_api.json")


def show(obj, indent=0, depth=4):
    p = "  " * indent
    if indent >= depth:
        print(p + "...")
        return
    if isinstance(obj, dict):
        for k, v in list(obj.items())[:10]:
            if isinstance(v, (dict, list)):
                print(p + str(k) + ":")
                show(v, indent + 1, depth)
            else:
                print(p + str(k) + ": " + str(v)[:80])
    elif isinstance(obj, list):
        print(p + f"[{len(obj)} items]")
        if obj:
            print(p + "first:")
            show(obj[0], indent + 1, depth)


show(data)
