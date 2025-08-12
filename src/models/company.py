"""
Company data model for SEC filings.
"""

from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class Company:
    """Represents a company that files with the SEC."""
    
    ticker: str
    name: str
    cik: Optional[str] = None
    sic: Optional[str] = None
    sic_description: Optional[str] = None
    
    def __post_init__(self):
        """Validate and normalize company data after initialization."""
        self.ticker = self.ticker.upper().strip()
        self.name = self.name.strip()
        
        if self.cik:
            self.cik = self._normalize_cik(self.cik)
    
    def _normalize_cik(self, cik: str) -> str:
        """Normalize CIK to 10-digit format with leading zeros."""
        # Remove any non-digit characters
        cik_clean = re.sub(r'\D', '', cik)
        
        # Pad with leading zeros to 10 digits
        return cik_clean.zfill(10)
    
    @property
    def is_valid(self) -> bool:
        """Check if the company has valid required fields."""
        return bool(self.ticker and self.name)
    
    @property
    def has_cik(self) -> bool:
        """Check if the company has a CIK number."""
        return bool(self.cik)
    
    def to_dict(self) -> dict:
        """Convert company to dictionary representation."""
        return {
            'ticker': self.ticker,
            'name': self.name,
            'cik': self.cik,
            'sic': self.sic,
            'sic_description': self.sic_description
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Company':
        """Create company instance from dictionary."""
        return cls(
            ticker=data.get('ticker', ''),
            name=data.get('name', ''),
            cik=data.get('cik'),
            sic=data.get('sic'),
            sic_description=data.get('sic_description')
        )
    
    def __str__(self) -> str:
        """String representation of the company."""
        return f"{self.ticker} ({self.name})"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"Company(ticker='{self.ticker}', name='{self.name}', cik='{self.cik}')"
