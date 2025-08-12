"""SEC EDGAR API client."""

import requests
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup

from ..models.filing import Filing, FilingType
from ..models.company import Company
from ..utils.config import Config
from ..utils.logger import get_logger
from ..utils.helpers import rate_limit_delay


class SECClient:
    """Client for SEC EDGAR database."""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = get_logger(__name__)
        self.session = requests.Session()
        
        sec_config = self.config.get_sec_config()
        self.search_url = sec_config.get('search_url', 'https://www.sec.gov/cgi-bin/browse-edgar')
        self.user_agent = sec_config.get('user_agent', 'SEC Downloader yourname@example.com')
        self.requests_per_second = sec_config.get('rate_limit', {}).get('requests_per_second', 10)
        
        # Set proper headers for SEC
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    def get_company_filings(self, company: Company, filing_type: FilingType = FilingType.ANNUAL_REPORT) -> List[Filing]:
        """Get filings for a company."""
        if not company.has_cik:
            self.logger.error(f"Company {company.ticker} does not have a CIK")
            return []
        
        self.logger.info(f"Searching for {filing_type.value} filings for {company.ticker} (CIK: {company.cik})")
        
        params = {
            'action': 'getcompany',
            'CIK': company.cik,
            'type': filing_type.value,
            'dateb': '',
            'datea': '',
            'owner': 'exclude',
            'output': 'xml',
            'count': '100'
        }
        
        try:
            rate_limit_delay(self.requests_per_second)
            self.logger.debug(f"Making request to SEC with params: {params}")
            
            response = self.session.get(self.search_url, params=params, timeout=30)
            response.raise_for_status()
            
            self.logger.debug(f"SEC response status: {response.status_code}")
            self.logger.debug(f"SEC response content length: {len(response.text)}")
            
            return self._parse_filings_response(response.text, company)
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to get filings for {company.ticker}: {e}")
            return []
    
    def _parse_filings_response(self, xml_content: str, company: Company) -> List[Filing]:
        """Parse XML response."""
        filings = []
        
        try:
            # Try to parse as XML first
            soup = BeautifulSoup(xml_content, 'xml')
            
            # Look for filing elements
            filing_elements = soup.find_all('filing')
            self.logger.debug(f"Found {len(filing_elements)} filing elements")
            
            if not filing_elements:
                # Try alternative parsing if no filing elements found
                self.logger.debug("No filing elements found, trying alternative parsing")
                return self._parse_alternative_response(xml_content, company)
            
            for filing_element in filing_elements:
                filing = self._parse_filing_info(filing_element, company)
                if filing:
                    filings.append(filing)
                    self.logger.debug(f"Parsed filing: {filing.accession_number} - {filing.filing_date}")
            
        except Exception as e:
            self.logger.error(f"Failed to parse XML response: {e}")
            # Try alternative parsing
            return self._parse_alternative_response(xml_content, company)
        
        self.logger.info(f"Successfully parsed {len(filings)} filings for {company.ticker}")
        return filings
    
    def _parse_alternative_response(self, content: str, company: Company) -> List[Filing]:
        """Parse response using alternative method (HTML parsing)."""
        filings = []
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Look for table rows with filing information
            rows = soup.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    # Look for filing date and document links
                    date_cell = cells[1] if len(cells) > 1 else None
                    link_cell = cells[2] if len(cells) > 2 else None
                    
                    if date_cell and link_cell:
                        try:
                            # Extract date
                            date_text = date_cell.get_text(strip=True)
                            if re.match(r'\d{4}-\d{2}-\d{2}', date_text):
                                filing_date = datetime.strptime(date_text, '%Y-%m-%d')
                                
                                # Extract document link
                                link = link_cell.find('a')
                                if link and 'href' in link.attrs:
                                    document_url = link['href']
                                    if not document_url.startswith('http'):
                                        document_url = 'https://www.sec.gov' + document_url
                                    
                                    # Generate accession number from URL
                                    accession_match = re.search(r'/(\d{10}-\d{2}-\d{6})/', document_url)
                                    accession_number = accession_match.group(1) if accession_match else f"unknown-{len(filings)}"
                                    
                                    filing = Filing(
                                        accession_number=accession_number,
                                        filing_type=FilingType.ANNUAL_REPORT,
                                        filing_date=filing_date,
                                        company_name=company.name,
                                        company_cik=company.cik,
                                        document_url=document_url,
                                        file_name=document_url.split('/')[-1]
                                    )
                                    filings.append(filing)
                                    self.logger.debug(f"Parsed filing from HTML: {accession_number}")
                        except Exception as e:
                            self.logger.debug(f"Error parsing row: {e}")
                            continue
            
        except Exception as e:
            self.logger.error(f"Failed to parse alternative response: {e}")
        
        return filings
    
    def _parse_filing_info(self, filing_element, company: Company) -> Optional[Filing]:
        """Parse filing info from XML element."""
        try:
            # Get filing date
            filing_date_elem = filing_element.find('dateFiled')
            document_url = filing_element.find('filingHREF')
            
            if not all([filing_date_elem, document_url]):
                self.logger.debug("Missing required filing elements")
                return None
            
            # Parse filing date
            filing_date = datetime.strptime(filing_date_elem.text.strip(), '%Y-%m-%d')
            document_url = document_url.text.strip()
            
            # Extract accession number from URL
            # Pattern: 0000320193-23-000106-index.htm -> 0000320193-23-000106
            accession_match = re.search(r'(\d{10}-\d{2}-\d{6})', document_url)
            
            if not accession_match:
                self.logger.debug(f"Could not extract accession number from URL: {document_url}")
                return None
            
            accession_number = accession_match.group(1)
            file_name = document_url.split('/')[-1]
            
            # Get filing type
            filing_type_elem = filing_element.find('type')
            filing_type = FilingType.ANNUAL_REPORT  # Default
            if filing_type_elem:
                type_text = filing_type_elem.text.strip()
                try:
                    filing_type = FilingType(type_text)
                except ValueError:
                    self.logger.debug(f"Unknown filing type: {type_text}")
            
            return Filing(
                accession_number=accession_number,
                filing_type=filing_type,
                filing_date=filing_date,
                company_name=company.name,
                company_cik=company.cik,
                document_url=document_url,
                file_name=file_name
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing filing info: {e}")
            return None
    
    def download_filing_content(self, filing: Filing) -> Optional[bytes]:
        """Download filing content."""
        try:
            self.logger.info(f"Downloading filing: {filing.file_name}")
            rate_limit_delay(self.requests_per_second)
            
            # First, download the index page
            response = self.session.get(filing.document_url, timeout=30)
            response.raise_for_status()
            
            # Parse the index page to find the main document URL
            main_doc_url = self._extract_main_document_url(response.text, filing.document_url)
            if not main_doc_url:
                self.logger.warning(f"Could not find main document URL in index page")
                return response.content  # Return index page as fallback
            
            # Download the main document
            self.logger.info(f"Downloading main document: {main_doc_url}")
            rate_limit_delay(self.requests_per_second)
            
            doc_response = self.session.get(main_doc_url, timeout=30)
            doc_response.raise_for_status()
            
            self.logger.info(f"Successfully downloaded {len(doc_response.content)} bytes")
            return doc_response.content
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to download filing {filing.accession_number}: {e}")
            return None
    
    def _extract_main_document_url(self, index_content: str, base_url: str) -> Optional[str]:
        """Extract the main document URL from the index page."""
        try:
            soup = BeautifulSoup(index_content, 'html.parser')
            
            # Look for the main 10-K document link
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                link_text = link.get_text(strip=True)
                
                # Look for the main 10-K document (not exhibits)
                if '/ix?doc=' in href and not 'exhibit' in link_text.lower():
                    # Extract the document path
                    doc_path = href.split('/ix?doc=')[1]
                    
                    # Convert to full URL
                    if doc_path.startswith('/'):
                        full_url = 'https://www.sec.gov' + doc_path
                    else:
                        full_url = 'https://www.sec.gov/' + doc_path
                    
                    self.logger.debug(f"Found main document URL: {full_url}")
                    return full_url
            
            self.logger.debug("No main document URL found in index page")
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting main document URL: {e}")
            return None
