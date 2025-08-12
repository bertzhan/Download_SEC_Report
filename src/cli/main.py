"""
Command-line interface for SEC Annual Report Downloader.
"""

import click
import logging
import csv
from datetime import datetime
from typing import List
from pathlib import Path

from ..core.downloader import SECDownloader
from ..models.company import Company
from ..utils.config import Config
from ..utils.logger import setup_logger, get_logger
from ..utils.helpers import validate_ticker, parse_date


@click.group()
@click.option('--config', '-c', help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cli(config, verbose):
    """SEC Annual Report Downloader"""
    # Setup logging
    setup_logger()
    if verbose:
        logger = get_logger()
        logger.setLevel(logging.DEBUG)
        # Also set console handler to DEBUG
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.DEBUG)


@cli.command()
@click.option('--company', '-t', help='Company ticker symbol')
@click.option('--companies', '-l', help='Comma-separated list of company tickers')
@click.option('--year', '-y', type=int, help='Year to download')
@click.option('--start-date', help='Start date (YYYY-MM-DD)')
@click.option('--end-date', help='End date (YYYY-MM-DD)')
@click.option('--output-dir', '-o', help='Output directory')
@click.option('--all', is_flag=True, help='Download all configured companies')
@click.option('--csv', help='CSV file with company tickers (format: ticker,name,cik)')
def download(company, companies, year, start_date, end_date, output_dir, all, csv):
    """Download SEC annual reports."""
    config = Config()
    
    if output_dir:
        config.get_paths_config()['downloads'] = output_dir
    
    downloader = SECDownloader(config)
    
    # Parse company list
    company_list = []
    if company:
        company_list.append(company)
    elif companies:
        company_list = [c.strip() for c in companies.split(',')]
    elif all:
        # Get all configured companies
        mappings = config.get_company_mappings()
        company_list = list(mappings.keys())
        click.echo(f"Downloading all {len(company_list)} configured companies")
    elif csv:
        # Load companies from CSV file
        company_list = load_companies_from_csv(csv)
        if not company_list:
            click.echo("Error: No valid companies found in CSV file")
            return
        click.echo(f"Loaded {len(company_list)} companies from CSV file")
    else:
        click.echo("Error: Must specify either --company, --companies, --all, or --csv")
        return
    
    # Validate tickers
    valid_companies = []
    for ticker in company_list:
        if not validate_ticker(ticker):
            click.echo(f"Warning: Invalid ticker format: {ticker}")
            continue
        
        # Get company info
        company_info = Company(ticker=ticker, name=ticker)
        mappings = config.get_company_mappings()
        if ticker.upper() in mappings:
            company_info.cik = mappings[ticker.upper()]
        
        valid_companies.append(company_info)
    
    if not valid_companies:
        click.echo("Error: No valid companies to process")
        return
    
    # Download reports
    if year:
        click.echo(f"Downloading annual reports for year {year}")
        
        # Track progress
        total_companies = len(valid_companies)
        successful_downloads = 0
        failed_downloads = 0
        
        for i, company in enumerate(valid_companies, 1):
            click.echo(f"[{i}/{total_companies}] Processing {company.ticker}...")
            
            try:
                filing = downloader.download_annual_report(company, year)
                if filing:
                    click.echo(f"  ✓ Downloaded: {company.ticker} {filing.filing_type.value} {year} (HTML)")
                    successful_downloads += 1
                else:
                    click.echo(f"  ✗ Failed: {company.ticker} {year}")
                    failed_downloads += 1
            except Exception as e:
                click.echo(f"  ✗ Error downloading {company.ticker}: {e}")
                failed_downloads += 1
        
        # Summary
        click.echo(f"\nDownload Summary:")
        click.echo(f"  Total companies: {total_companies}")
        click.echo(f"  Successful: {successful_downloads}")
        click.echo(f"  Failed: {failed_downloads}")
        click.echo(f"  Success rate: {(successful_downloads/total_companies)*100:.1f}%")
    else:
        click.echo("Error: Must specify --year")
        return


def load_companies_from_csv(csv_path: str) -> List[str]:
    """Load company tickers from CSV file."""
    companies = []
    
    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            # Check if required columns exist
            if 'ticker' not in reader.fieldnames:
                click.echo("Error: CSV must have 'ticker' column")
                return []
            
            for row in reader:
                ticker = row['ticker'].strip().upper()
                if ticker and validate_ticker(ticker):
                    companies.append(ticker)
                else:
                    click.echo(f"Warning: Invalid ticker '{ticker}' in CSV, skipping")
    
    except FileNotFoundError:
        click.echo(f"Error: CSV file '{csv_path}' not found")
        return []
    except Exception as e:
        click.echo(f"Error reading CSV file: {e}")
        return []
    
    return companies


@cli.command()
def list_companies():
    """List available companies."""
    config = Config()
    mappings = config.get_company_mappings()
    
    click.echo("Available companies:")
    for ticker, cik in mappings.items():
        click.echo(f"  {ticker}: {cik}")


@cli.command()
def version():
    """Show version information."""
    from .. import __version__
    click.echo(f"SEC Annual Report Downloader v{__version__}")


if __name__ == '__main__':
    cli()
