"""
Validation utilities for SEC filings.
"""

from typing import Optional
from ..models.filing import Filing
from ..utils.helpers import get_file_size_mb


class FilingValidator:
    """Validator for SEC filings."""
    
    @staticmethod
    def validate_filing(filing: Filing) -> bool:
        """Validate filing data."""
        if not filing.accession_number:
            return False
        if not filing.document_url:
            return False
        if not filing.company_cik:
            return False
        return True
    
    @staticmethod
    def validate_downloaded_file(filing: Filing, min_size_mb: float = 0.001) -> bool:
        """Validate downloaded file."""
        if not filing.local_path:
            return False
        
        file_size_mb = get_file_size_mb(filing.local_path)
        return file_size_mb >= min_size_mb
