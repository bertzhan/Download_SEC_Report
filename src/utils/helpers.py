"""
Helper utility functions for the SEC downloader.
"""

import re
import time
from datetime import datetime, date
from typing import Optional, List
from pathlib import Path


def normalize_cik(cik: str) -> str:
    """Normalize CIK to 10-digit format with leading zeros."""
    cik_clean = re.sub(r'\D', '', cik)
    return cik_clean.zfill(10)


def validate_ticker(ticker: str) -> bool:
    """Validate stock ticker format."""
    if not ticker:
        return False
    return bool(re.match(r'^[A-Z]{1,5}$', ticker.upper()))


def parse_date(date_str: str) -> Optional[date]:
    """Parse date string in various formats."""
    formats = [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%Y%m%d'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    return None


def rate_limit_delay(requests_per_second: int = 10) -> None:
    """Implement rate limiting delay."""
    time.sleep(1.0 / requests_per_second)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system usage."""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename


def get_file_size_mb(file_path: str) -> float:
    """Get file size in megabytes."""
    try:
        size_bytes = Path(file_path).stat().st_size
        return size_bytes / (1024 * 1024)
    except (OSError, FileNotFoundError):
        return 0.0


def create_directory_structure(base_path: str, company_ticker: str, year: int) -> Path:
    """Create directory structure for downloads."""
    download_path = Path(base_path) / company_ticker / str(year)
    download_path.mkdir(parents=True, exist_ok=True)
    return download_path


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def extract_year_from_filename(filename: str) -> Optional[int]:
    """Extract year from filename."""
    year_pattern = r'(\d{4})'
    match = re.search(year_pattern, filename)
    if match:
        return int(match.group(1))
    return None


def is_valid_url(url: str) -> bool:
    """Check if URL is valid."""
    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return bool(re.match(url_pattern, url))
