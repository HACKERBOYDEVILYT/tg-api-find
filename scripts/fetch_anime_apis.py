import json
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "public-apis.json"
NEW_PATH = ROOT / "data" / "new-apis.json"

# নতুন অ্যানিম এবং এনিমে স্ট্রিমিং এপিআই পাওয়ার ওপেন সোর্স সোর্স URL
ANIME_SOURCES = [
    "https://raw.githubusercontent.com/public-apis/public-apis/master/data/anime.json",
    "https://raw.githubusercontent.com/fawazahmed0/currency-api/1/latest/currencies.json" # উদাহরণস্বরূপ সোর্স URL
]

def load_existing():
    if DATA_PATH.exists():
        try:
            return json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def fetch_anime_apis():
    headers = {"User-Agent": "PublicAPIExplorerBot/1.0"}
    discovered = []

    # GitHub Open Source Raw APIs থেকে ডেটা ফেচ করা
    url = "https://raw.githubusercontent.com/public-apis/public-apis/master/data/anime.json"
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            for entry in data.get("entries", []):
                # অ্যানিম ও স্ট্রিমিং কি-ওয়ার্ড চেক
                name = entry.get("API", "")
                desc = entry.get("Description", "")
                
                discovered.append({
                    "name": name,
                    "category": "Anime / Streaming",
                    "purpose": desc,
                    "auth": entry.get("Auth") or "No",
                    "pricing": "Free" if not entry.get("HTTPS") else "Unknown",
                    "base_url": entry.get("Link", ""),
                    "documentation_url": entry.get("Link", ""),
                    "spec_url": "",
                    "source": "Open-Source Anime Directory",
                    "profile_status": "Active"
                })
    except Exception as e:
        print(f"Error fetching anime APIs: {e}")

    return discovered

def main():
    existing = load_existing()
    existing_urls = {item.get("documentation_url") for item in existing if item.get("documentation_url")}
    
    new_found = fetch_anime_apis()
    
    # পুরোনো ডেটার সাথে মিলিয়ে নতুন এপিআই ফিল্টার করা
    truly_new = []
    for item in new_found:
        if item.get("documentation_url") not in existing_urls:
            truly_new.append(item)
            existing.append(item)
            existing_urls.add(item.get("documentation_url"))

    if truly_new:
        print(f"New anime APIs discovered: {len(truly_new)}")
        
        # public-apis.json আপডেট করা
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        
        # নতুন ফেচ করা এপিআইগুলো new-apis.json এ রাখা (যাতে টেলিগ্রাম নোটিফিকেশন যায়)
        NEW_PATH.write_text(json.dumps(truly_new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        print("No new anime APIs found.")

if __name__ == "__main__":
    main()
