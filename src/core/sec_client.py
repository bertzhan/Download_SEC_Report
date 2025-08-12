"""SEC EDGAR API client."""

import requests
import re
import os
from datetime import datetime
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path

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
        """Download filing content with embedded images."""
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
            
            # Process the HTML to download images and update references
            processed_content = self._process_html_with_images(doc_response.content, main_doc_url, filing)
            
            self.logger.info(f"Successfully downloaded and processed {len(processed_content)} bytes")
            return processed_content
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to download filing {filing.accession_number}: {e}")
            return None
    
    def _detect_encoding(self, content: bytes) -> str:
        """Detect the encoding of HTML content."""
        try:
            # Try to detect encoding from HTML meta tags first
            soup = BeautifulSoup(content, 'html.parser')
            meta_charset = soup.find('meta', charset=True)
            if meta_charset:
                return meta_charset['charset']
            
            # Try to detect encoding from meta http-equiv
            meta_equiv = soup.find('meta', attrs={'http-equiv': 'Content-Type'})
            if meta_equiv and 'charset=' in meta_equiv.get('content', ''):
                content_attr = meta_equiv['content']
                charset_start = content_attr.find('charset=') + 8
                charset_end = content_attr.find(';', charset_start)
                if charset_end == -1:
                    charset_end = len(content_attr)
                return content_attr[charset_start:charset_end].strip()
            
            # Fallback to UTF-8 (most common for modern web content)
            return 'utf-8'
        except Exception:
            # Ultimate fallback
            return 'utf-8'
    
    def _process_html_with_images(self, html_content: bytes, base_url: str, filing: Filing) -> bytes:
        """Process HTML content to download images and update references."""
        try:
            # Get download configuration
            download_config = self.config.get_download_config()
            download_images = download_config.get('download_images', True)
            download_css = download_config.get('download_css', True)
            create_resource_folders = download_config.get('create_resource_folders', True)
            
            # Detect encoding and decode content
            encoding = self._detect_encoding(html_content)
            self.logger.debug(f"Detected encoding: {encoding}")
            
            try:
                html_text = html_content.decode(encoding)
            except UnicodeDecodeError:
                # Fallback to UTF-8 if detected encoding fails
                self.logger.warning(f"Failed to decode with {encoding}, trying UTF-8")
                html_text = html_content.decode('utf-8', errors='replace')
            
            # Parse HTML
            soup = BeautifulSoup(html_text, 'html.parser')
            
            # Ensure proper encoding in the HTML
            if not soup.find('meta', charset=True):
                # Add charset meta tag if missing
                meta_charset = soup.new_tag('meta', charset='utf-8')
                if soup.head:
                    soup.head.insert(0, meta_charset)
                else:
                    # Create head if it doesn't exist
                    head = soup.new_tag('head')
                    head.insert(0, meta_charset)
                    soup.html.insert(0, head)
            
            # Find all image tags
            img_tags = soup.find_all('img')
            self.logger.info(f"Found {len(img_tags)} image tags in HTML")
            
            # Find all link tags (for CSS files)
            link_tags = soup.find_all('link', rel='stylesheet')
            self.logger.info(f"Found {len(link_tags)} stylesheet links in HTML")
            
            # Create resources directory relative to the filing
            if filing.local_path:
                filing_dir = Path(filing.local_path).parent
                if create_resource_folders:
                    resources_dir = filing_dir / 'resources'
                    images_dir = resources_dir / 'images'
                    css_dir = resources_dir / 'css'
                    images_dir.mkdir(parents=True, exist_ok=True)
                    css_dir.mkdir(parents=True, exist_ok=True)
                else:
                    # Simple flat structure
                    images_dir = filing_dir / 'images'
                    css_dir = filing_dir / 'css'
                    images_dir.mkdir(exist_ok=True)
                    css_dir.mkdir(exist_ok=True)
            else:
                # This should not happen anymore, but keep as safety
                self.logger.warning("filing.local_path is not set, using fallback directory")
                if create_resource_folders:
                    resources_dir = Path('data/downloads/resources')
                    images_dir = resources_dir / 'images'
                    css_dir = resources_dir / 'css'
                    images_dir.mkdir(parents=True, exist_ok=True)
                    css_dir.mkdir(parents=True, exist_ok=True)
                else:
                    images_dir = Path('data/downloads/images')
                    css_dir = Path('data/downloads/css')
                    images_dir.mkdir(parents=True, exist_ok=True)
                    css_dir.mkdir(exist_ok=True)
            
            # Process each image if enabled
            if download_images:
                for i, img_tag in enumerate(img_tags):
                    src = img_tag.get('src')
                    if not src:
                        continue
                    
                    # Convert relative URL to absolute
                    absolute_url = urljoin(base_url, src)
                    
                    # Download image
                    local_image_path = self._download_image(absolute_url, images_dir, i)
                    
                    if local_image_path:
                        # Update the image src to point to local file
                        if create_resource_folders:
                            relative_path = f"resources/images/{local_image_path.name}"
                        else:
                            relative_path = f"images/{local_image_path.name}"
                        img_tag['src'] = relative_path
                        self.logger.debug(f"Updated image src: {src} -> {relative_path}")
            
            # Process each stylesheet if enabled
            if download_css:
                for i, link_tag in enumerate(link_tags):
                    href = link_tag.get('href')
                    if not href:
                        continue
                    
                    # Convert relative URL to absolute
                    absolute_url = urljoin(base_url, href)
                    
                    # Download CSS file
                    local_css_path = self._download_css_file(absolute_url, css_dir, i)
                    
                    if local_css_path:
                        # Update the href to point to local file
                        if create_resource_folders:
                            relative_path = f"resources/css/{local_css_path.name}"
                        else:
                            relative_path = f"css/{local_css_path.name}"
                        link_tag['href'] = relative_path
                        self.logger.debug(f"Updated CSS href: {href} -> {relative_path}")
            
            # Return processed HTML
            return str(soup).encode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Error processing HTML with images: {e}")
            return html_content  # Return original content if processing fails
    
    def _download_image(self, image_url: str, images_dir: Path, index: int) -> Optional[Path]:
        """Download an image and return the local path."""
        try:
            self.logger.debug(f"Downloading image: {image_url}")
            rate_limit_delay(self.requests_per_second)
            
            response = self.session.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Determine file extension from URL or content type
            parsed_url = urlparse(image_url)
            path = parsed_url.path
            extension = Path(path).suffix if Path(path).suffix else '.jpg'
            
            # Generate filename
            filename = f"image_{index:03d}{extension}"
            local_path = images_dir / filename
            
            # Save image
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            self.logger.debug(f"Downloaded image: {local_path}")
            return local_path
            
        except Exception as e:
            self.logger.error(f"Failed to download image {image_url}: {e}")
            return None
    
    def _download_css_file(self, css_url: str, css_dir: Path, index: int) -> Optional[Path]:
        """Download a CSS file and return the local path."""
        try:
            self.logger.debug(f"Downloading CSS file: {css_url}")
            rate_limit_delay(self.requests_per_second)
            
            response = self.session.get(css_url, timeout=30)
            response.raise_for_status()
            
            # Determine file extension
            parsed_url = urlparse(css_url)
            path = parsed_url.path
            extension = Path(path).suffix if Path(path).suffix else '.css'
            
            # Generate filename
            filename = f"stylesheet_{index:03d}{extension}"
            local_path = css_dir / filename
            
            # Process CSS content to download embedded images
            processed_css_content = self._process_css_with_images(response.content, css_url, css_dir)
            
            # Save processed CSS file
            with open(local_path, 'wb') as f:
                f.write(processed_css_content)
            
            self.logger.debug(f"Downloaded and processed CSS file: {local_path}")
            return local_path
            
        except Exception as e:
            self.logger.error(f"Failed to download CSS file {css_url}: {e}")
            return None
    
    def _process_css_with_images(self, css_content: bytes, css_url: str, css_dir: Path) -> bytes:
        """Process CSS content to download embedded images and update references."""
        try:
            # Get download configuration
            download_config = self.config.get_download_config()
            download_resources = download_config.get('download_resources', True)
            
            if not download_resources:
                return css_content  # Return original content if resource downloading is disabled
            
            css_text = css_content.decode('utf-8', errors='ignore')
            
            # Find all url() references in CSS
            url_pattern = r'url\(["\']?([^"\')\s]+)["\']?\)'
            matches = re.findall(url_pattern, css_text)
            
            self.logger.debug(f"Found {len(matches)} URL references in CSS")
            
            # Process each URL reference
            for i, url in enumerate(matches):
                # Skip data URLs and absolute URLs that are not relative to SEC
                if url.startswith('data:') or url.startswith('http'):
                    continue
                
                # Convert relative URL to absolute
                absolute_url = urljoin(css_url, url)
                
                # Download the resource (could be image, font, etc.)
                local_resource_path = self._download_css_resource(absolute_url, css_dir, i)
                
                if local_resource_path:
                    # Update the URL reference in CSS
                    relative_path = local_resource_path.name
                    css_text = css_text.replace(f'url({url})', f'url({relative_path})')
                    css_text = css_text.replace(f'url("{url}")', f'url("{relative_path}")')
                    css_text = css_text.replace(f"url('{url}')", f"url('{relative_path}')")
                    self.logger.debug(f"Updated CSS URL: {url} -> {relative_path}")
            
            return css_text.encode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Error processing CSS with images: {e}")
            return css_content  # Return original content if processing fails
    
    def _download_css_resource(self, resource_url: str, css_dir: Path, index: int) -> Optional[Path]:
        """Download a resource referenced in CSS and return the local path."""
        try:
            self.logger.debug(f"Downloading CSS resource: {resource_url}")
            rate_limit_delay(self.requests_per_second)
            
            response = self.session.get(resource_url, timeout=30)
            response.raise_for_status()
            
            # Determine file extension from URL or content type
            parsed_url = urlparse(resource_url)
            path = parsed_url.path
            extension = Path(path).suffix if Path(path).suffix else '.bin'
            
            # Generate filename
            filename = f"resource_{index:03d}{extension}"
            local_path = css_dir / filename
            
            # Save resource
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            self.logger.debug(f"Downloaded CSS resource: {local_path}")
            return local_path
            
        except Exception as e:
            self.logger.error(f"Failed to download CSS resource {resource_url}: {e}")
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
