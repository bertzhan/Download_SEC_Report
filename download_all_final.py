#!/usr/bin/env python3
"""
Simple script to download all companies from company.csv
"""

import csv
import time
import requests
from src.core.downloader import SECDownloader
from src.models.company import Company
from src.utils.config import Config
from src.utils.logger import setup_logger, get_logger

def download_all_sec_companies():
    """Download ALL company CIK numbers from SEC."""
    print("Downloading complete SEC company database...")
    
    try:
        # SEC company ticker lookup
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        # Build complete ticker to CIK mapping
        ticker_to_cik = {}
        company_details = {}
        
        for key, company_info in data.items():
            ticker = company_info.get('ticker', '').upper()
            name = company_info.get('title', '')
            cik_str = str(company_info.get('cik_str', ''))
            
            if ticker and cik_str:
                # Use the cik_str field and pad to 10 digits
                cik_padded = cik_str.zfill(10)
                ticker_to_cik[ticker] = cik_padded
                company_details[ticker] = {
                    'name': name,
                    'cik': cik_padded,
                    'cik_raw': cik_str
                }
        
        print(f"Downloaded {len(ticker_to_cik)} companies from SEC database")
        
        # Save to file for future use
        import json
        with open('sec_companies_database.json', 'w') as f:
            json.dump(company_details, f, indent=2)
        
        print("Saved SEC company database to sec_companies_database.json")
        
        return ticker_to_cik, company_details
        
    except Exception as e:
        print(f"Error downloading SEC company database: {e}")
        return {}, {}

def load_sec_companies_database():
    """Load SEC companies database from file or download if not exists."""
    import json
    import os
    
    # Try to load from file first
    if os.path.exists('sec_companies_database.json'):
        try:
            with open('sec_companies_database.json', 'r') as f:
                company_details = json.load(f)
            
            ticker_to_cik = {}
            for ticker, details in company_details.items():
                # Pad CIK to 10 digits for SEC API compatibility
                cik_raw = str(details['cik'])  # Convert to string first
                cik_padded = cik_raw.zfill(10)
                ticker_to_cik[ticker] = cik_padded
            
            print(f"Loaded {len(ticker_to_cik)} companies from cached database")
            return ticker_to_cik, company_details
        except Exception as e:
            print(f"Error loading cached database: {e}")
    
    # Download if file doesn't exist or is corrupted
    return download_all_sec_companies()

def get_cik_from_sec(ticker: str, sec_database=None):
    """Get CIK number for a company ticker from SEC database."""
    if sec_database is None:
        sec_database, _ = load_sec_companies_database()
    
    return sec_database.get(ticker.upper())



def download_all_companies(csv_path="company.csv", year=2023, max_companies=None):
    """Download all companies from CSV"""
    
    setup_logger()
    config = Config()
    downloader = SECDownloader(config)
    
    # Load complete SEC company database
    print("Loading SEC company database...")
    sec_database, company_details = load_sec_companies_database()
    
    companies = []
    
    # Load companies from CSV
    with open(csv_path, 'r') as file:
        reader = csv.DictReader(file)
        count = 0
        
        for row in reader:
            if max_companies and count >= max_companies:
                break
                
            ticker = row['symbol'].strip().upper()
            name = row.get('name', '').strip()
            
            # Skip invalid tickers
            if not ticker or len(ticker) > 5 or any(c in ticker for c in ['-', '/', '^', '.']):
                continue
            
            # Get CIK from SEC database
            cik = sec_database.get(ticker)
            if cik:
                print(f"  ✓ Found CIK for {ticker}: {cik}")
                companies.append({
                    'ticker': ticker,
                    'name': name,
                    'cik': cik
                })
                count += 1
            else:
                print(f"  ✗ No CIK found for {ticker}")
    
    print(f"Found {len(companies)} companies with CIK numbers from SEC database")
    
    # Download reports
    successful = 0
    failed = 0
    
    for i, company_data in enumerate(companies, 1):
        ticker = company_data['ticker']
        name = company_data['name']
        cik = company_data['cik']
        
        print(f"[{i}/{len(companies)}] Processing {ticker} ({name})...")
        
        try:
            company = Company(ticker=ticker, name=name, cik=cik)
            filing = downloader.download_annual_report(company, year)
            
            if filing:
                print(f"  ✓ Downloaded: {ticker} 10-K {year}")
                successful += 1
            else:
                print(f"  ✗ Failed: {ticker}")
                failed += 1
                
        except Exception as e:
            print(f"  ✗ Error: {ticker} - {e}")
            failed += 1
        
        time.sleep(0.1)  # Rate limiting
    
    print(f"\nSummary: {successful} successful, {failed} failed")
    return successful, failed

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="company.csv")
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--max", type=int)
    
    args = parser.parse_args()
    
    print("Downloading all companies from CSV...")
    download_all_companies(args.csv, args.year, args.max)
