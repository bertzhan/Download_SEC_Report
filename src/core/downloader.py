"""Main downloader orchestration for SEC filings."""

from datetime import date
from typing import List, Optional
from pathlib import Path

from ..models.company import Company
from ..models.filing import Filing, FilingType
from ..utils.config import Config
from ..utils.logger import get_logger
from ..utils.helpers import create_directory_structure, sanitize_filename
from .sec_client import SECClient


class SECDownloader:
    """Main downloader for SEC filings."""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = get_logger(__name__)
        self.sec_client = SECClient(config)
        
        # Ensure directories exist
        self.config.ensure_directories()
    
    def download_annual_report(self, company: Company, year: int) -> Optional[Filing]:
        """Download annual report for a specific year."""
        self.logger.info(f"Downloading annual report for {company.ticker} ({year})")
        
        # Get filings for the company
        filings = self.sec_client.get_company_filings(company, FilingType.ANNUAL_REPORT)
        
        # Filter by year
        year_filings = [f for f in filings if f.filing_year == year]
        
        if not year_filings:
            self.logger.warning(f"No annual reports found for {company.ticker} in {year}")
            return None
        
        # Get the most recent filing
        latest_filing = max(year_filings, key=lambda f: f.filing_date)
        
        # Download the filing
        return self._download_filing(latest_filing, company)
    
    def download_multiple_companies(self, companies: List[Company], year: int) -> List[Filing]:
        """Download annual reports for multiple companies."""
        results = []
        
        for company in companies:
            try:
                filing = self.download_annual_report(company, year)
                if filing:
                    results.append(filing)
            except Exception as e:
                self.logger.error(f"Failed to download for {company.ticker}: {e}")
        
        return results
    
    def _download_filing(self, filing: Filing, company: Company) -> Optional[Filing]:
        """Download a specific filing."""
        try:
            # Get download path
            paths_config = self.config.get_paths_config()
            download_base = paths_config.get('downloads', 'data/downloads')
            
            # Create directory structure
            download_dir = create_directory_structure(download_base, company.ticker, filing.filing_year)
            
            # Generate filename
            filename = filing.get_expected_filename(company.ticker, 'html')
            filename = sanitize_filename(filename)
            file_path = download_dir / filename
            
            # Check if file already exists
            download_config = self.config.get_download_config()
            if file_path.exists() and not download_config.get('overwrite_existing', False):
                self.logger.info(f"File already exists: {file_path}")
                filing.local_path = str(file_path)
                return filing
            
            # Set local_path BEFORE downloading content so image processing knows where to create resources
            filing.local_path = str(file_path)
            
            # Download content
            content = self.sec_client.download_filing_content(filing)
            if not content:
                return None
            
            # Save file with proper UTF-8 encoding
            with open(file_path, 'wb') as f:
                f.write(content)
            
            self.logger.info(f"Successfully downloaded: {file_path}")
            return filing
            
        except Exception as e:
            self.logger.error(f"Failed to download filing: {e}")
            return None
