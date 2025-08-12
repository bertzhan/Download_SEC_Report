# SEC Annual Report Downloader

A Python application for downloading annual reports (10-K filings) from the U.S. Securities and Exchange Commission (SEC) EDGAR database.

## Features

- Download annual reports (10-K) for specified companies
- Support for multiple companies and date ranges
- Configurable download options (formats, date filters)
- Rate limiting to comply with SEC guidelines
- Error handling and retry mechanisms
- Progress tracking and logging
- Data validation and integrity checks

## Architecture Overview

```
Download_Sec_Report/
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── sec_client.py          # SEC EDGAR API client
│   │   ├── downloader.py          # Main download orchestration
│   │   └── validator.py           # Data validation utilities
│   ├── models/
│   │   ├── __init__.py
│   │   ├── filing.py              # Filing data models
│   │   └── company.py             # Company data models
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py              # Configuration management
│   │   ├── logger.py              # Logging utilities
│   │   └── helpers.py             # Helper functions
│   └── cli/
│       ├── __init__.py
│       └── main.py                # Command-line interface
├── config/
│   └── settings.yaml              # Configuration file
├── data/
│   ├── downloads/                 # Downloaded reports
│   └── logs/                      # Application logs
├── tests/
│   ├── __init__.py
│   ├── test_sec_client.py
│   ├── test_downloader.py
│   └── test_validator.py
├── requirements.txt
├── setup.py
└── README.md
```

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure settings in `config/settings.yaml`

## Usage

### Command Line Interface

```bash
# Download 10-K for a specific company
python -m src.cli.main download --company AAPL --year 2023

# Download multiple companies
python -m src.cli.main download --companies AAPL,MSFT,GOOGL --year 2023

# Download with date range
python -m src.cli.main download --company AAPL --start-date 2023-01-01 --end-date 2023-12-31
```

### Programmatic Usage

```python
from src.core.downloader import SECDownloader
from src.models.company import Company

# Initialize downloader
downloader = SECDownloader()

# Download annual report
company = Company(ticker="AAPL", name="Apple Inc.")
filing = downloader.download_annual_report(company, year=2023)
```

## Configuration

Edit `config/settings.yaml` to customize:

- SEC API endpoints
- Rate limiting settings
- Download paths
- Logging configuration
- Retry policies

## Rate Limiting

The application respects SEC's rate limiting guidelines:
- 10 requests per second
- User-Agent header required
- Automatic retry with exponential backoff

## Error Handling

- Network connectivity issues
- Invalid company tickers
- Missing filings
- Rate limit violations
- File corruption

## Testing

Run tests with:
```bash
python -m pytest tests/
```

## License

MIT License
