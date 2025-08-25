from urllib.request import urlopen
import certifi
import json
import os
import tqdm
from datetime import datetime, date
import time


def get_jsonparsed_data(url):
    response = urlopen(url, cafile=certifi.where())
    data = response.read().decode("utf-8")
    return json.loads(data)


def load_company(path):
    f = open(path)
    lines = f.readlines()
    lines = lines[1:]
    companies = [t.split(",")[0] for t in lines]
    return companies


def save_statement(stype:str, path:str, company:str, api_key:str = 'K9lR2FFwXrJJfDR1RChYZltMCVN9NzYU'):
    urls = {"income": "https://financialmodelingprep.com/api/v3/income-statement/{company}?period=annual&apikey={api_key}",
            "balance": "https://financialmodelingprep.com/api/v3/balance-sheet-statement/{company}?period=annual&apikey={api_key}",
            "cashflow": "https://financialmodelingprep.com/api/v3/cash-flow-statement/{company}?period=annual&apikey={api_key}"}
    url = urls[stype].format(company=company, api_key=api_key)
    data = get_jsonparsed_data(url)
    keys = data[0].keys()
    spath = os.path.join(path, company)

    if not os.path.exists(spath):
        os.makedirs(spath)
    f = open(os.path.join(spath, stype+'.csv'), 'w')
    f.write(",".join(keys) + "\n")
    for item in data:
        line = [item[k] for k in keys]
        line = ",".join([str(t) for t in line])
        f.write(line + "\n")
    f.close()


def load_progress(progress_file):
    """Load progress from JSON file"""
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {
        "last_processed_index": -1,
        "last_processed_date": None,
        "daily_api_calls": 0,
        "total_companies_processed": 0,
        "companies": []
    }


def save_progress(progress_file, progress_data):
    """Save progress to JSON file"""
    with open(progress_file, 'w') as f:
        json.dump(progress_data, f, indent=2)


def reset_daily_counter_if_needed(progress_data):
    """Reset daily API call counter if it's a new day"""
    today = date.today().isoformat()
    if progress_data["last_processed_date"] != today:
        progress_data["daily_api_calls"] = 0
        progress_data["last_processed_date"] = today
    return progress_data


def check_api_limit(progress_data, calls_needed=3):
    """Check if we can make the required API calls today"""
    if progress_data["daily_api_calls"] + calls_needed > 240:
        return False
    return True


def main(start_id=None, end_id=None):
    companies = load_company('data/company.csv')
    progress_file = "./data/progress.json"
    path = "./data/sec_statements"
    
    # Create data directory if it doesn't exist
    os.makedirs(path, exist_ok=True)
    
    # Load progress
    progress = load_progress(progress_file)
    progress = reset_daily_counter_if_needed(progress)
    
    # Determine start and end indices
    if start_id is None:
        start_id = progress["last_processed_index"] + 1
    if end_id is None:
        end_id = len(companies)
    
    # Validate indices
    start_id = max(0, start_id)
    end_id = min(len(companies), end_id)
    
    print(f"Starting from company index {start_id} (resuming from last run)")
    print(f"Processing companies {start_id} to {end_id-1} out of {len(companies)} total")
    print(f"Daily API calls used today: {progress['daily_api_calls']}")
    
    # Process companies
    for i in tqdm.trange(start_id, end_id):
        company = companies[i]
        # Check if we have enough API calls left for today
        if not check_api_limit(progress, calls_needed=3):
            print(f"\n⚠️  Daily API limit reached ({progress['daily_api_calls']}). Stopping for today.")
            print(f"Last processed company: {company} (index {i})")
            print(f"Resume tomorrow to continue from index {i}")
            break
        try:
            print(f"\nProcessing {i}: {company}")
            # Process all three statement types for this company
            for stype in ["income", "balance", "cashflow"]:
                save_statement(stype, path, company)
                progress["daily_api_calls"] += 1
                print(f"  ✓ Downloaded {stype} statement")

            # Update progress
            progress["last_processed_index"] = i
            progress["total_companies_processed"] += 1
            progress["companies"].append({
                "index": i,
                "symbol": company,
                "processed_at": datetime.now().isoformat()
            })

            # Save progress after each company
            save_progress(progress_file, progress)
            print(f"  ✓ Progress saved - API calls used: {progress['daily_api_calls']}")

            # Small delay to be respectful to the API
            time.sleep(0.5)
        except Exception as e:
            print(f"  ✗ Error processing {company}: {str(e)}")
            # Still save progress to avoid losing track
            continue
    
    # Final summary
    print(f"\n📊 Summary:")
    print(f"   Companies processed in this session: {progress['total_companies_processed']}")
    print(f"   Total API calls used today: {progress['daily_api_calls']}")
    print(f"   Last processed index: {progress['last_processed_index']}")
    
    if progress["last_processed_index"] < end_id - 1:
        print(f"   ⏰ Resume tomorrow to continue from index {progress['last_processed_index'] + 1}")


if __name__ == "__main__":
    main()  # Resume from last position
