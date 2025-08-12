"""
Filing data model for SEC documents.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List
import os


class FilingType(Enum):
    """Enumeration of SEC filing types."""
    ANNUAL_REPORT = "10-K"
    QUARTERLY_REPORT = "10-Q"
    CURRENT_REPORT = "8-K"
    AMENDMENT = "10-K/A"
    
    @classmethod
    def get_annual_reports(cls) -> List['FilingType']:
        return [cls.ANNUAL_REPORT, cls.AMENDMENT]


@dataclass
class Filing:
    """Represents an SEC filing document."""
    
    accession_number: str
    filing_type: FilingType
    filing_date: datetime
    company_name: str
    company_cik: str
    document_url: str
    file_name: str
    file_size: Optional[int] = None
    description: Optional[str] = None
    local_path: Optional[str] = None
    download_timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if isinstance(self.filing_type, str):
            try:
                self.filing_type = FilingType(self.filing_type)
            except ValueError:
                raise ValueError(f"Invalid filing type: {self.filing_type}")
    
    @property
    def is_annual_report(self) -> bool:
        return self.filing_type in FilingType.get_annual_reports()
    
    @property
    def filing_year(self) -> int:
        return self.filing_date.year
    
    @property
    def is_downloaded(self) -> bool:
        return bool(self.local_path and os.path.exists(self.local_path))
    
    def get_expected_filename(self, company_ticker: str, format_type: str = 'html') -> str:
        year = self.filing_year
        filing_type = self.filing_type.value.replace('/', '')
        return f"{company_ticker}_{filing_type}_{year}.{format_type}"
    
    def __str__(self) -> str:
        return f"{self.filing_type.value} - {self.company_name} ({self.filing_date.strftime('%Y-%m-%d')})"
