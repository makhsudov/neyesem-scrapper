import json
import os
import sys
from difflib import SequenceMatcher


def load_source(city: str, source: str) -> dict:
    path = os.path.join("output", city, source)
    restaurants = {}
    if not os.path.isdir(path):
        print(f"Directory not found: {path}")
        return restaurants

    for fname in os.listdir(path):
        if fname.endswith(".json"):
            with open(os.path.join(path, fname), encoding="utf-8") as f:
                r = json.load(f)
                restaurants[r["name"]] = r
    return restaurants


def name_similarity(a: str, b: str) -> float:
    """Calculate similarity between two restaurant names"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def match_restaurants(source_a: dict, source_b: dict, threshold: float = 0.75) -> list:
    """Match restaurants between two sources by name similarity"""
    matches = []
    for name_a, r_a in source_a.items():
        best_score, best_b = 0.0, None
        for name_b, r_b in source_b.items():
            score = name_similarity(name_a, name_b)
            if score > best_score:
                best_score, best_b = score, r_b
        if best_score >= threshold and best_b:
            matches.append((r_a, best_b, best_score))
    return matches


def compare_menus(r_a: dict, r_b: dict) -> list:
    """Compare menu items and find price differences"""
    def extract_items(r):
        return {
            i["name"]: i["price"]
            for cat in r.get("menu", {}).get("categories", [])
            for i in cat.get("items", [])
        }

    items_a = extract_items(r_a)
    items_b = extract_items(r_b)

    diffs = []
    for name, price_a in items_a.items():
        if name in items_b and price_a is not None and items_b[name] is not None:
            diff = items_b[name] - price_a
            if abs(diff) > 0.01:
                diffs.append({
                    "item": name,
                    "price_a": price_a,
                    "price_b": items_b[name],
                    "diff": round(diff, 2),
                })
    return diffs


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage:   python compare.py <city> <source_A> <source_B>")
        print("Example: python compare.py bursa getir_yemek yemeksepeti")
        sys.exit(1)

    city, src_a, src_b = sys.argv[1], sys.argv[2], sys.argv[3]

    print(f"\nLoading {src_a} and {src_b} data for city: {city}...")
    restaurants_a = load_source(city, src_a)
    restaurants_b = load_source(city, src_b)

    print(f"  {src_a}: {len(restaurants_a)} restaurants")
    print(f"  {src_b}: {len(restaurants_b)} restaurants")

    matches = match_restaurants(restaurants_a, restaurants_b)
    print(f"\nMatched restaurants: {len(matches)}")

    found_diffs = 0
    for r_a, r_b, score in sorted(matches, key=lambda x: x[0]["name"]):
        diffs = compare_menus(r_a, r_b)
        if not diffs:
            continue

        found_diffs += 1
        print(f"\n{r_a['name']} (similarity: {score:.0%})")
        for d in sorted(diffs, key=lambda x: abs(x["diff"]), reverse=True):
            sign = "+" if d["diff"] > 0 else ""
            print(f"  {d['item'][:50]:<50}  {src_a}={d['price_a']:.2f}₺   "
                  f"{src_b}={d['price_b']:.2f}₺   ({sign}{d['diff']}₺)")

    if found_diffs == 0:
        print("No price differences found.")