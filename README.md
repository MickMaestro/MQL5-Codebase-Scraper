# MQL5-Codebase-Scrapers

A collection of Python web scrapers for downloading MQL5 trading code from the official MQL5.com Codebase. These scripts automatically download Expert Advisors, Indicators, Scripts, and Libraries along with their documentation and metadata.

## Overview

This repository contains 4 scrapers that download different types of MQL5 code:

1. **Expert Advisor Fetcher** - Downloads automated trading systems (Expert Advisors/EAs)
2. **Indicator Fetcher** - Downloads technical indicators
3. **Script Fetcher** - Downloads utility scripts
4. **Library Fetcher** - Downloads code libraries

Each scraper downloads the complete package including ZIP files, source code, descriptions, author information, ratings, and statistics.

## Features

- **Automatic Organization** - Creates separate folders for each downloaded item
- **Complete Metadata** - Extracts descriptions, author info, ratings, views, downloads, publication dates
- **Rate Limiting** - Built-in intelligent rate limiting to respect MQL5.com servers
  - Random delays between 2-5 seconds per request
  - Extended delays of 8-13 seconds between pages
  - Progressive delays for high request counts
  - Automatic retry on HTTP 429 (rate limit) responses
- **Error Handling** - Robust error handling with automatic retries
- **Resume Support** - Can be interrupted (Ctrl+C) and restarted from a different page
- **Progress Tracking** - Real-time progress updates and request rate monitoring

## Requirements

```bash
pip install requests beautifulsoup4
```

**Dependencies:**
- `requests` - For making HTTP requests
- `beautifulsoup4` - For parsing HTML content
- `lxml` - HTML parser (optional but recommended)

## Installation

1. Clone this repository or download the Python files
2. Install required dependencies:
   ```bash
   pip install requests beautifulsoup4
   ```
3. Navigate to the directory containing the scripts

## Usage

### 1. Expert Advisor Fetcher

Downloads automated trading systems (Expert Advisors) from MQL5.com.

**Location:** `MQL5 Expert Advisors/MT5 Expert Advisor Fetcher.py`

**Run:**
```bash
cd "MQL5 Expert Advisors"
python "MT5 Expert Advisor Fetcher.py"
```

**Downloads:**
- ZIP file containing the complete EA package
- Comprehensive text file with:
  - Full description and features
  - Author name, username, and profile URL
  - User ratings and views
  - Publication and update dates
  - File size and version information
  - Download count

**Configuration:**
Edit the `main()` function in the script:
```python
max_pages = 4  # Number of pages to scrape
start_page = 1  # Starting page number
```

### 2. Indicator Fetcher

Downloads technical indicators for chart analysis.

**Location:** `MQL5 Indicators/MT5 Indicator Fetcher.py`

**Run:**
```bash
cd "MQL5 Indicators"
python "MT5 Indicator Fetcher.py"
```

**Downloads:**
- ZIP file containing the indicator code
- Text file with indicator description and metadata

**Configuration:**
```python
max_pages = 5  # Number of pages to scrape
start_page = 1  # Starting page number
```

### 3. Script Fetcher

Downloads utility scripts for various trading tasks.

**Location:** `MQL5 Scripts/MT5 Script Fetcher.py`

**Run:**
```bash
cd "MQL5 Scripts"
python "MT5 Script Fetcher.py"
```

**Downloads:**
- ZIP file containing the script archive
- Individual source files (.mq5, .mq4, .txt, etc.)
- Text file with script description, ratings, and statistics

**Configuration:**
```python
max_pages = 8  # Number of pages to scrape
start_page = 1  # Starting page number
```

### 4. Library Fetcher

Downloads reusable code libraries for MQL5 development.

**Location:** `MQL5 Libraries/MT5 Library Fetcher.py`

**Run:**
```bash
cd "MQL5 Libraries"
python "MT5 Library Fetcher.py"
```

**Downloads:**
- ZIP file containing the library archive
- Individual source files (.mq5, .mq4, .mqh, .txt, etc.)
- Text file with comprehensive information:
  - Library name, ID, and URL
  - Author information
  - Ratings, views, downloads, favorites, comments
  - Publication date and version
  - Complete description

**Configuration:**
```python
max_pages = 3  # Number of pages to scrape
start_page = 1  # Starting page number
```

## Output Structure

Each scraper creates folders in the same directory as the script. For example:

```
MQL5 Expert Advisors/
├── MT5 Expert Advisor Fetcher.py
├── Moving Average EA/
│   ├── Moving Average EA.zip
│   └── Moving Average EA description.txt
├── Bollinger Bands EA/
│   ├── Bollinger Bands EA.zip
│   └── Bollinger Bands EA description.txt
└── ...
```

## Rate Limiting & Best Practices

All scrapers include comprehensive rate limiting to be respectful of MQL5.com servers:

- **Start small:** Begin with 2-3 pages to test
- **Monitor output:** Watch for rate limit warnings
- **Be patient:** The scrapers intentionally run slowly to avoid server overload
- **Resume capability:** If interrupted, change `start_page` to continue

## Stopping & Resuming

To stop a scraper at any time, press `Ctrl+C`. To resume:

1. Open the Python file
2. Find the configuration section in `main()`
3. Set `start_page` to where you want to resume
4. Run the script again

Example:
```python
max_pages = 10   # Scrape up to page 10
start_page = 5   # Resume from page 5
```

## Troubleshooting

**Problem:** Script fails with connection error
- **Solution:** Check your internet connection and try again

**Problem:** Getting rate limited (HTTP 429)
- **Solution:** The script will automatically wait 60 seconds and retry

**Problem:** Missing dependencies
- **Solution:** Run `pip install requests beautifulsoup4`

**Problem:** No description found for some items
- **Solution:** Some items on MQL5.com have minimal descriptions - this is normal

**Problem:** Unicode/encoding errors
- **Solution:** The scripts handle UTF-8 encoding automatically, but some files may have encoding issues from the source

## Notes

- Each page contains approximately 40 items
- Download time varies based on file sizes and network speed
- The scrapers save files in the same directory as the script
- Filenames are automatically cleaned to be filesystem-safe
- All scrapers use realistic browser headers to avoid detection

## Legal & Ethical Considerations

- These scrapers are for personal use and educational purposes
- Respect MQL5.com's Terms of Service
- The built-in rate limiting is designed to be respectful of their servers
- Do not modify the rate limiting to make requests faster
- Downloaded code is subject to the original author's license terms

## Contributing

Feel free to open issues or submit pull requests for improvements.

## License

These scripts are provided as-is for educational purposes. Downloaded content is subject to the original author's license terms on MQL5.com.

## Disclaimer

This tool is not affiliated with or endorsed by MQL5.com. Use at your own risk. Always verify the legitimacy and safety of downloaded code before using it in live trading.
