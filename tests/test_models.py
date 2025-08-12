"""
Tests for data models.
"""

import pytest
from datetime import datetime
from src.models.company import Company
from src.models.filing import Filing, FilingType


class TestCompany:
    """Test Company model."""
    
    def test_company_creation(self):
        """Test basic company creation."""
        company = Company(ticker="AAPL", name="Apple Inc.", cik="320193")
        assert company.ticker == "AAPL"
        assert company.name == "Apple Inc."
        assert company.cik == "0000320193"
    
    def test_cik_normalization(self):
        """Test CIK normalization."""
        company = Company(ticker="MSFT", name="Microsoft", cik="789019")
        assert company.cik == "0000789019"
    
    def test_company_validation(self):
        """Test company validation."""
        valid_company = Company(ticker="GOOGL", name="Alphabet Inc.")
        assert valid_company.is_valid
        
        invalid_company = Company(ticker="", name="")
        assert not invalid_company.is_valid


class TestFiling:
    """Test Filing model."""
    
    def test_filing_creation(self):
        """Test basic filing creation."""
        filing = Filing(
            accession_number="0000320193-23-000010",
            filing_type=FilingType.ANNUAL_REPORT,
            filing_date=datetime(2023, 10, 27),
            company_name="Apple Inc.",
            company_cik="0000320193",
            document_url="https://www.sec.gov/Archives/edgar/data/320193/000032019323000010/aapl-20230930.htm",
            file_name="aapl-20230930.htm"
        )
        
        assert filing.accession_number == "0000320193-23-000010"
        assert filing.filing_type == FilingType.ANNUAL_REPORT
        assert filing.is_annual_report
        assert filing.filing_year == 2023
    
    def test_filing_type_enum(self):
        """Test filing type enumeration."""
        assert FilingType.ANNUAL_REPORT.value == "10-K"
        assert FilingType.QUARTERLY_REPORT.value == "10-Q"
        
        annual_types = FilingType.get_annual_reports()
        assert FilingType.ANNUAL_REPORT in annual_types
        assert FilingType.AMENDMENT in annual_types
