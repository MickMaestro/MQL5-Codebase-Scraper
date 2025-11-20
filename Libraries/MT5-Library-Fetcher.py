import requests
from bs4 import BeautifulSoup
import os
import re
import time
import random
from urllib.parse import urljoin, urlparse
import zipfile
from pathlib import Path

class MQL5Scraper:
    def __init__(self, base_url="https://www.mql5.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        # Rate limiting settings
        self.min_delay = 2.0  # Minimum delay between requests (seconds)
        self.max_delay = 5.0  # Maximum delay between requests (seconds)
        self.page_delay = 8.0  # Extra delay between pages (seconds)
        self.request_count = 0
        self.start_time = time.time()
        
        # Set download directory to the same folder as this script
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"Download directory: {self.script_dir}")
        
    def clean_filename(self, filename):
        """Clean filename to be safe for filesystem"""
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip()
        return filename[:100]  # Limit length
    
    def smart_delay(self, is_page_request=False):
        """Implement intelligent delays with randomization to avoid rate limiting"""
        self.request_count += 1
        
        if is_page_request:
            delay = self.page_delay + random.uniform(2, 5)  # Extra delay for page requests
        else:
            delay = random.uniform(self.min_delay, self.max_delay)
        
        # Add progressive delay if making many requests
        if self.request_count > 50:
            delay += 2.0
        elif self.request_count > 100:
            delay += 4.0
        
        # Show rate limiting info
        elapsed_time = time.time() - self.start_time
        requests_per_minute = (self.request_count / elapsed_time) * 60
        
        print(f"Rate limiting: waiting {delay:.1f}s (Request #{self.request_count}, {requests_per_minute:.1f} req/min)")
        time.sleep(delay)
    
    def safe_request(self, url, is_page_request=False):
        """Make a request with rate limiting and error handling"""
        try:
            self.smart_delay(is_page_request)
            response = self.session.get(url, timeout=30)
            
            # Check for rate limiting responses
            if response.status_code == 429:
                print("Rate limited! Waiting 60 seconds before retrying...")
                time.sleep(60)
                response = self.session.get(url, timeout=30)
            
            return response
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
    
    def get_indicator_links(self, page=1):
        """Get all indicator links from a specific page"""
        url = f"{self.base_url}/en/code/mt5/indicators"
        if page > 1:
            url += f"/page{page}"
            
        print(f"Fetching page {page}...")
        response = self.safe_request(url, is_page_request=True)
        
        if not response or response.status_code != 200:
            print(f"Failed to get page {page}: status {response.status_code if response else 'No response'}")
            return []
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all indicator links
        indicator_links = []
        links = soup.find_all('a', href=re.compile(r'/en/code/\d+$'))
        
        for link in links:
            href = link.get('href')
            title = link.get_text(strip=True)
            if href and title:
                full_url = urljoin(self.base_url, href)
                indicator_links.append({
                    'url': full_url,
                    'title': title,
                    'id': href.split('/')[-1]
                })
        
        return indicator_links
    
    def scrape_indicator_page(self, indicator_url, indicator_title, indicator_id):
        """Scrape individual indicator page for zip file and description"""
        print(f"Scraping indicator: {indicator_title}")
        
        response = self.safe_request(indicator_url)
        if not response or response.status_code != 200:
            print(f"Failed to get indicator page: {response.status_code if response else 'No response'}")
            return False
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Create folder for this indicator in the script directory
        folder_name = self.clean_filename(indicator_title)
        folder_path = os.path.join(self.script_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # Find download link
        download_link = None
        zip_links = soup.find_all('a', href=re.compile(r'/en/code/download/\d+\.zip'))
        if zip_links:
            download_link = urljoin(self.base_url, zip_links[0].get('href'))
        
        # Download zip file if found
        if download_link:
            try:
                print(f"Downloading zip file...")
                zip_response = self.safe_request(download_link)
                if zip_response and zip_response.status_code == 200:
                    zip_filename = os.path.join(folder_path, f"{folder_name}.zip")
                    with open(zip_filename, 'wb') as f:
                        f.write(zip_response.content)
                    print(f"Downloaded: {zip_filename}")
                else:
                    print(f"Failed to download zip: {zip_response.status_code if zip_response else 'No response'}")
            except Exception as e:
                print(f"Error downloading zip: {e}")
        
        # Extract description - look for main content area
        description_text = ""
        
        # Try to find the main description in various ways
        description_candidates = []
        
        # Look for specific elements that might contain the description
        main_content = soup.find('div', class_='content')
        if main_content:
            # Get all paragraph text from main content
            paragraphs = main_content.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 30:  # Only a good amount of text
                    description_candidates.append(text)
        
        # Try to get description from meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            description_candidates.insert(0, meta_desc.get('content'))
        
        # Look for any div with substantial text that's not navigation/header
        if not description_candidates:
            all_divs = soup.find_all('div')
            for div in all_divs:
                # Skip common navigation/header classes
                div_class = div.get('class', [])
                if any(cls in str(div_class).lower() for cls in ['nav', 'header', 'footer', 'menu', 'sidebar']):
                    continue
                    
                text = div.get_text(strip=True)
                if text and len(text) > 50 and len(text) < 2000:  # Reasonable description length
                    description_candidates.append(text)
        
        # Use the best description candidate
        if description_candidates:
            description_text = description_candidates[0]
            # Clean up the text
            description_text = re.sub(r'\s+', ' ', description_text)  # Normalize whitespace
            description_text = description_text[:1000]  # Limit length
        else:
            description_text = f"No detailed description found for {indicator_title} (ID: {indicator_id})\nURL: {indicator_url}"
        
        # Save description to text file
        description_filename = os.path.join(folder_path, f"{folder_name} description.txt")
        try:
            with open(description_filename, 'w', encoding='utf-8') as f:
                f.write(f"Indicator: {indicator_title}\n")
                f.write(f"URL: {indicator_url}\n")
                f.write(f"ID: {indicator_id}\n")
                f.write("-" * 50 + "\n\n")
                f.write(description_text)
            print(f"Saved description: {description_filename}")
        except Exception as e:
            print(f"Error saving description: {e}")
        
        return True
    
    def scrape_all_indicators(self, max_pages=5, start_page=1):
        """Scrape all indicators from multiple pages"""
        print(f"Starting to scrape MQL5 indicators (pages {start_page}-{max_pages})...")
        
        total_indicators = 0
        
        for page in range(start_page, max_pages + 1):
            try:
                indicator_links = self.get_indicator_links(page)
                
                if not indicator_links:
                    print(f"No indicators found on page {page}, stopping...")
                    break
                
                print(f"Found {len(indicator_links)} indicators on page {page}")
                total_indicators += len(indicator_links)
                
                for i, indicator in enumerate(indicator_links, 1):
                    print(f"[Page {page}, Item {i}/{len(indicator_links)}] Processing: {indicator['title']}")
                    
                    success = self.scrape_indicator_page(
                        indicator['url'],
                        indicator['title'],
                        indicator['id']
                    )
                    
                    if success:
                        print(f"Successfully processed: {indicator['title']}")
                    else:
                        print(f"Failed to process: {indicator['title']}")
                
                print(f"Completed page {page}. Taking a longer break before next page...")
                time.sleep(random.uniform(10, 15))  # Longer delay between pages
                
            except KeyboardInterrupt:
                print("\nScraping interrupted by user")
                break
            except Exception as e:
                print(f"Error on page {page}: {e}")
                continue
        
        print(f"\nScraping completed! Processed {total_indicators} indicators.")

def main():
    scraper = MQL5Scraper()
    
    # These parameters can be modified as needed:
    # - max_pages: How many pages to scrape (each page has ~40 indicators)
    # - start_page: Which page to start from
    
    print("MQL5 Indicator Scraper")
    print("=" * 50)
    print("This will scrape indicators from https://www.mql5.com/en/code/mt5/indicators")
    print("Each indicator will be saved in its own folder with:")
    print("- ZIP file containing the indicator code")
    print("- Text file with the indicator description")
    print()
    
    # Configuration - Conservative settings to avoid rate limiting
    max_pages = 5  # Change this to scrape more pages (start small!)
    start_page = 1  # Change this to start from a different page
    
    print("RATE LIMITING ENABLED")
    print("This scraper includes multiple rate limiting measures:")
    print("- Random delays between 2-5 seconds per request")
    print("- Extended delays of 8-13 seconds between pages")
    print("- Progressive delays for high request counts")
    print("- Automatic retry on HTTP 429 (rate limit) responses")
    print("- Realistic browser headers to avoid detection")
    print()
    
    print(f"Scraping pages {start_page} to {max_pages} (approximately {(max_pages - start_page + 1) * 40} indicators)")
    print("Press Ctrl+C to stop at any time")
    print()
    
    scraper.scrape_all_indicators(max_pages=max_pages, start_page=start_page)

if __name__ == "__main__":
    main()
