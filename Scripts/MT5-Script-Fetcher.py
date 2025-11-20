import requests
from bs4 import BeautifulSoup
import os
import re
import time
import random
from urllib.parse import urljoin, urlparse
import zipfile
from pathlib import Path

class MQL5ScriptScraper:
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
        """Implement intelligent delays with randomisation to avoid rate limiting"""
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
    
    def get_script_links(self, page=1):
        """Get all script links from a specific page"""
        url = f"{self.base_url}/en/code/mt5/scripts"
        if page > 1:
            url += f"/page{page}"
            
        print(f"Fetching page {page}...")
        response = self.safe_request(url, is_page_request=True)
        
        if not response or response.status_code != 200:
            print(f"Failed to get page {page}: status {response.status_code if response else 'No response'}")
            return []
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all script links
        script_links = []
        links = soup.find_all('a', href=re.compile(r'/en/code/\d+$'))
        
        for link in links:
            href = link.get('href')
            title = link.get_text(strip=True)
            if href and title:
                full_url = urljoin(self.base_url, href)
                script_links.append({
                    'url': full_url,
                    'title': title,
                    'id': href.split('/')[-1]
                })
        
        return script_links
    
    def extract_description_and_rating(self, soup):
        """Extract description text between 'Go to Freelance' and 'Go to Discussion' markers and user ratings"""
        description_text = ""
        rating_info = {}
        
        # Convert soup to text to work with string patterns
        page_text = soup.get_text()
        
        # Extract description between markers
        freelance_pattern = r'Go to Freelance.*?(?=Go to Discussion|$)'
        match = re.search(freelance_pattern, page_text, re.DOTALL | re.IGNORECASE)
        
        if match:
            description_section = match.group(0)
            # Clean up and extract meaningful content
            lines = description_section.split('\n')
            meaningful_lines = []
            
            for line in lines:
                line = line.strip()
                # Skip navigation and common UI text
                if (line and 
                    not line.startswith('Go to') and 
                    'Freelance' not in line and
                    len(line) > 10 and
                    not line.isdigit()):
                    meaningful_lines.append(line)
            
            description_text = '\n'.join(meaningful_lines)
        
        # If no description found between markers, try alternative methods
        if not description_text:
            # Look for meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                description_text = meta_desc.get('content')
            
            # Try to find main content div
            if not description_text:
                main_content = soup.find('div', class_='content')
                if main_content:
                    paragraphs = main_content.find_all('p')
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if text and len(text) > 30:
                            description_text = text
                            break
        
        # Extract rating information
        try:
            # Look for views
            views_match = re.search(r'Views:\s*(\d+)', page_text, re.IGNORECASE)
            if views_match:
                rating_info['views'] = int(views_match.group(1))
            
            # Look for rating (various patterns)
            rating_patterns = [
                r'Rating:\s*\((\d+(?:\.\d+)?)\s*out\s*of\s*(\d+)\)',
                r'(\d+(?:\.\d+)?)\s*out\s*of\s*(\d+)',
                r'Rating:\s*(\d+(?:\.\d+)?)/(\d+)'
            ]
            
            for pattern in rating_patterns:
                rating_match = re.search(pattern, page_text, re.IGNORECASE)
                if rating_match:
                    rating_info['rating'] = float(rating_match.group(1))
                    rating_info['max_rating'] = int(rating_match.group(2))
                    break
            
            # Look for publish date
            date_patterns = [
                r'Published:\s*(\d+\s+\w+\s+\d+)',
                r'(\d+\s+\w+\s+\d+,?\s*\d+:\d+)'
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, page_text, re.IGNORECASE)
                if date_match:
                    rating_info['published'] = date_match.group(1)
                    break
            
            # Look for download count or popularity metrics
            downloads_match = re.search(r'Downloads?:\s*(\d+)', page_text, re.IGNORECASE)
            if downloads_match:
                rating_info['downloads'] = int(downloads_match.group(1))
                
        except Exception as e:
            print(f"Error extracting rating info: {e}")
        
        return description_text, rating_info
    
    def scrape_script_page(self, script_url, script_title, script_id):
        """Scrape individual script page for zip file, source files, and description"""
        print(f"Scraping script: {script_title}")
        
        response = self.safe_request(script_url)
        if not response or response.status_code != 200:
            print(f"Failed to get script page: {response.status_code if response else 'No response'}")
            return False
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Create folder for this script in the script directory
        folder_name = self.clean_filename(script_title)
        folder_path = os.path.join(self.script_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # Find download links for ZIP files
        zip_download_link = None
        zip_links = soup.find_all('a', href=re.compile(r'/en/code/download/\d+\.zip'))
        if zip_links:
            zip_download_link = urljoin(self.base_url, zip_links[0].get('href'))
        
        # Find download links for source files (.mq5, .txt, etc.)
        source_links = []
        source_file_links = soup.find_all('a', href=re.compile(r'/en/code/download/\d+/[^/]+\.(mq5|mq4|txt|ex5|ex4)$'))
        for link in source_file_links:
            source_links.append({
                'url': urljoin(self.base_url, link.get('href')),
                'filename': link.get('href').split('/')[-1]
            })
        
        # Download ZIP file if found
        if zip_download_link:
            try:
                print(f"Downloading ZIP file...")
                zip_response = self.safe_request(zip_download_link)
                if zip_response and zip_response.status_code == 200:
                    zip_filename = os.path.join(folder_path, f"{folder_name}.zip")
                    with open(zip_filename, 'wb') as f:
                        f.write(zip_response.content)
                    print(f"Downloaded: {zip_filename}")
                else:
                    print(f"Failed to download ZIP: {zip_response.status_code if zip_response else 'No response'}")
            except Exception as e:
                print(f"Error downloading ZIP: {e}")
        
        # Download individual source files
        for source in source_links:
            try:
                print(f"Downloading source file: {source['filename']}")
                source_response = self.safe_request(source['url'])
                if source_response and source_response.status_code == 200:
                    source_filename = os.path.join(folder_path, source['filename'])
                    
                    # Handle text files with UTF-8 encoding
                    if source['filename'].endswith('.txt') or source['filename'].endswith('.mq5') or source['filename'].endswith('.mq4'):
                        try:
                            with open(source_filename, 'w', encoding='utf-8') as f:
                                f.write(source_response.text)
                        except UnicodeDecodeError:
                            # Fallback to binary mode if UTF-8 fails
                            with open(source_filename, 'wb') as f:
                                f.write(source_response.content)
                    else:
                        with open(source_filename, 'wb') as f:
                            f.write(source_response.content)
                    
                    print(f"Downloaded: {source_filename}")
                else:
                    print(f"Failed to download {source['filename']}: {source_response.status_code if source_response else 'No response'}")
            except Exception as e:
                print(f"Error downloading {source['filename']}: {e}")
        
        # Extract description and rating information
        description_text, rating_info = self.extract_description_and_rating(soup)
        
        if not description_text:
            description_text = f"No detailed description found for {script_title} (ID: {script_id})\nURL: {script_url}"
        
        # Clean up the description text
        description_text = re.sub(r'\s+', ' ', description_text)  # Normalize whitespace
        description_text = description_text.strip()
        
        # Save description and rating to text file
        description_filename = os.path.join(folder_path, f"{folder_name} description.txt")
        try:
            with open(description_filename, 'w', encoding='utf-8') as f:
                f.write(f"Script: {script_title}\n")
                f.write(f"URL: {script_url}\n")
                f.write(f"ID: {script_id}\n")
                f.write("-" * 50 + "\n")
                
                # Add rating information if available
                if rating_info:
                    f.write("RATING INFORMATION:\n")
                    if 'views' in rating_info:
                        f.write(f"Views: {rating_info['views']}\n")
                    if 'rating' in rating_info and 'max_rating' in rating_info:
                        f.write(f"Rating: {rating_info['rating']}/{rating_info['max_rating']}\n")
                    if 'published' in rating_info:
                        f.write(f"Published: {rating_info['published']}\n")
                    if 'downloads' in rating_info:
                        f.write(f"Downloads: {rating_info['downloads']}\n")
                    f.write("-" * 50 + "\n")
                
                f.write("\nDESCRIPTION:\n")
                f.write(description_text)
                
            print(f"Saved description: {description_filename}")
        except Exception as e:
            print(f"Error saving description: {e}")
        
        return True
    
    def scrape_all_scripts(self, max_pages=5, start_page=1):
        """Scrape all scripts from multiple pages"""
        print(f"Starting to scrape MQL5 scripts (pages {start_page}-{max_pages})...")
        
        total_scripts = 0
        
        for page in range(start_page, max_pages + 1):
            try:
                script_links = self.get_script_links(page)
                
                if not script_links:
                    print(f"No scripts found on page {page}, stopping...")
                    break
                
                print(f"Found {len(script_links)} scripts on page {page}")
                total_scripts += len(script_links)
                
                for i, script in enumerate(script_links, 1):
                    print(f"[Page {page}, Item {i}/{len(script_links)}] Processing: {script['title']}")
                    
                    success = self.scrape_script_page(
                        script['url'],
                        script['title'],
                        script['id']
                    )
                    
                    if success:
                        print(f"Successfully processed: {script['title']}")
                    else:
                        print(f"Failed to process: {script['title']}")
                
                print(f"Completed page {page}. Taking a longer break before next page...")
                time.sleep(random.uniform(10, 15))  # Longer delay between pages
                
            except KeyboardInterrupt:
                print("\nScraping interrupted by user")
                break
            except Exception as e:
                print(f"Error on page {page}: {e}")
                continue
        
        print(f"\nScraping completed! Processed {total_scripts} scripts.")

def main():
    scraper = MQL5ScriptScraper()
    
    # These parameters can be modified as needed:
    # - max_pages: How many pages to scrape (each page has ~40 scripts)
    # - start_page: Which page to start from
    
    print("MQL5 Script Scraper")
    print("=" * 50)
    print("This will scrape scripts from https://www.mql5.com/en/code/mt5/scripts")
    print("Each script will be saved in its own folder with:")
    print("- ZIP file containing the script archive")
    print("- Individual source files (.mq5, .txt, etc.)")
    print("- Text file with script description and user ratings")
    print()
    
    # Configuration - Conservative settings to avoid rate limiting
    max_pages = 8  # Change this to scrape more pages (I recommend starting small)
    start_page = 1  # Change this to start from a different page
    
    print("RATE LIMITING ENABLED")
    print("This scraper includes multiple rate limiting measures:")
    print("- Random delays between 2-5 seconds per request")
    print("- Extended delays of 8-13 seconds between pages")
    print("- Progressive delays for high request counts")
    print("- Automatic retry on HTTP 429 (rate limit) responses")
    print("- Realistic browser headers to avoid detection")
    print()
    
    print(f"Scraping pages {start_page} to {max_pages} (approximately {(max_pages - start_page + 1) * 40} scripts)")
    print("Press Ctrl+C to stop at any time")
    print()
    
    scraper.scrape_all_scripts(max_pages=max_pages, start_page=start_page)

if __name__ == "__main__":
    main()
