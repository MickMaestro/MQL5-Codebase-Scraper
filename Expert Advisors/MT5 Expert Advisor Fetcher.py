import requests
from bs4 import BeautifulSoup
import os
import re
import time
import random
from urllib.parse import urljoin, urlparse
import zipfile
from pathlib import Path

class MQL5ExpertAdvisorScraper:
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
    
    def get_expert_advisor_links(self, page=1):
        """Get all expert advisor links from a specific page"""
        url = f"{self.base_url}/en/code/mt5/experts"
        if page > 1:
            url += f"/page{page}"
            
        print(f"Fetching page {page}...")
        response = self.safe_request(url, is_page_request=True)
        
        if not response or response.status_code != 200:
            print(f"Failed to get page {page}: status {response.status_code if response else 'No response'}")
            return []
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all expert advisor links
        ea_links = []
        links = soup.find_all('a', href=re.compile(r'/en/code/\d+$'))
        
        for link in links:
            href = link.get('href')
            title = link.get_text(strip=True)
            if href and title:
                full_url = urljoin(self.base_url, href)
                ea_links.append({
                    'url': full_url,
                    'title': title,
                    'id': href.split('/')[-1]
                })
        
        return ea_links
    
    def extract_author_info(self, soup):
        """Extract author name and profile information"""
        author_info = {}
        page_text = soup.get_text()
        
        try:
            # Look for author name patterns
            author_patterns = [
                r'Author:\s*([^\n\r]+)',
                r'by\s+([A-Za-z\s]+)',
                r'/en/users/([^/\s]+)'
            ]
            
            # Try to find author link
            author_links = soup.find_all('a', href=re.compile(r'/en/users/[^/]+$'))
            if author_links:
                author_link = author_links[0]
                author_info['profile_url'] = urljoin(self.base_url, author_link.get('href'))
                author_info['username'] = author_link.get('href').split('/')[-1]
                # Try to get display name from link text
                author_name = author_link.get_text(strip=True)
                if author_name:
                    author_info['name'] = author_name
            
            # Try regex patterns as backup
            if 'name' not in author_info:
                for pattern in author_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        author_info['name'] = match.group(1).strip()
                        break
                        
        except Exception as e:
            print(f"Error extracting author info: {e}")
        
        return author_info
    
    def extract_description_and_rating(self, soup):
        """Extract description text between 'Go to Freelance' and 'Go to Discussion' markers and comprehensive ratings"""
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
                    'Discussion' not in line and
                    len(line) > 10 and
                    not line.isdigit() and
                    'Need a robot' not in line):
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
        
        # Extract comprehensive rating and metadata information
        try:
            # Look for views
            views_patterns = [
                r'Views:\s*(\d+(?:,\d+)*)',
                r'(\d+(?:,\d+)*)\s*views'
            ]
            for pattern in views_patterns:
                views_match = re.search(pattern, page_text, re.IGNORECASE)
                if views_match:
                    rating_info['views'] = int(views_match.group(1).replace(',', ''))
                    break
            
            # Look for rating (various patterns)
            rating_patterns = [
                r'Rating:\s*\((\d+(?:\.\d+)?)\s*out\s*of\s*(\d+)\)',
                r'(\d+(?:\.\d+)?)\s*out\s*of\s*(\d+)',
                r'Rating:\s*(\d+(?:\.\d+)?)/(\d+)',
                r'(\d+(?:\.\d+)?)\s*stars'
            ]
            
            for pattern in rating_patterns:
                rating_match = re.search(pattern, page_text, re.IGNORECASE)
                if rating_match:
                    rating_info['rating'] = float(rating_match.group(1))
                    if len(rating_match.groups()) > 1:
                        rating_info['max_rating'] = int(rating_match.group(2))
                    break
            
            # Look for publish date
            date_patterns = [
                r'Published:\s*(\d+\s+\w+\s+\d+(?:,\s*\d+:\d+)?)',
                r'(\d+\s+\w+\s+\d+,?\s*\d+:\d+)'
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, page_text, re.IGNORECASE)
                if date_match:
                    rating_info['published'] = date_match.group(1)
                    break
            
            # Look for updated date
            update_patterns = [
                r'Updated:\s*(\d+\s+\w+\s+\d+(?:,\s*\d+:\d+)?)',
                r'Last\s+updated:\s*(\d+\s+\w+\s+\d+(?:,\s*\d+:\d+)?)'
            ]
            
            for pattern in update_patterns:
                update_match = re.search(pattern, page_text, re.IGNORECASE)
                if update_match:
                    rating_info['updated'] = update_match.group(1)
                    break
            
            # Look for file size
            size_patterns = [
                r'File\s+Size:\s*(\d+(?:\.\d+)?\s*[KMG]B)',
                r'Size:\s*(\d+(?:\.\d+)?\s*[KMG]B)',
                r'(\d+(?:\.\d+)?\s*[KMG]B)'
            ]
            
            for pattern in size_patterns:
                size_match = re.search(pattern, page_text, re.IGNORECASE)
                if size_match:
                    rating_info['file_size'] = size_match.group(1)
                    break
            
            # Look for version
            version_patterns = [
                r'Version:\s*(v?\d+(?:\.\d+)*)',
                r'(v\d+(?:\.\d+)*)'
            ]
            
            for pattern in version_patterns:
                version_match = re.search(pattern, page_text, re.IGNORECASE)
                if version_match:
                    rating_info['version'] = version_match.group(1)
                    break
            
            # Look for download count or popularity metrics
            downloads_match = re.search(r'Downloads?:\s*(\d+(?:,\d+)*)', page_text, re.IGNORECASE)
            if downloads_match:
                rating_info['downloads'] = int(downloads_match.group(1).replace(',', ''))
                
        except Exception as e:
            print(f"Error extracting rating info: {e}")
        
        return description_text, rating_info
    
    def scrape_expert_advisor_page(self, ea_url, ea_title, ea_id):
        """Scrape individual expert advisor page for zip file and comprehensive information"""
        print(f"Scraping Expert Advisor: {ea_title}")
        
        response = self.safe_request(ea_url)
        if not response or response.status_code != 200:
            print(f"Failed to get EA page: {response.status_code if response else 'No response'}")
            return False
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Create folder for this EA in the script directory
        folder_name = self.clean_filename(ea_title)
        folder_path = os.path.join(self.script_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # Find download link for ZIP file only (as requested)
        zip_download_link = None
        zip_links = soup.find_all('a', href=re.compile(r'/en/code/download/\d+\.zip'))
        if zip_links:
            zip_download_link = urljoin(self.base_url, zip_links[0].get('href'))
        
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
        else:
            print("No ZIP download link found")
        
        # Extract author information
        author_info = self.extract_author_info(soup)
        
        # Extract description and rating information
        description_text, rating_info = self.extract_description_and_rating(soup)
        
        if not description_text:
            description_text = f"No detailed description found for {ea_title} (ID: {ea_id})\nURL: {ea_url}"
        
        # Clean up the description text
        description_text = re.sub(r'\s+', ' ', description_text)  # Normalize whitespace
        description_text = description_text.strip()
        
        # Save comprehensive information to text file
        description_filename = os.path.join(folder_path, f"{folder_name} description.txt")
        try:
            with open(description_filename, 'w', encoding='utf-8') as f:
                f.write(f"Expert Advisor: {ea_title}\n")
                f.write(f"URL: {ea_url}\n")
                f.write(f"ID: {ea_id}\n")
                f.write("-" * 60 + "\n")
                
                # Add author information if available
                if author_info:
                    f.write("AUTHOR INFORMATION:\n")
                    if 'name' in author_info:
                        f.write(f"Name: {author_info['name']}\n")
                    if 'username' in author_info:
                        f.write(f"Username: {author_info['username']}\n")
                    if 'profile_url' in author_info:
                        f.write(f"Profile: {author_info['profile_url']}\n")
                    f.write("-" * 60 + "\n")
                
                # Add rating and metadata information if available
                if rating_info:
                    f.write("METADATA & RATINGS:\n")
                    if 'views' in rating_info:
                        f.write(f"Views: {rating_info['views']:,}\n")
                    if 'rating' in rating_info and 'max_rating' in rating_info:
                        f.write(f"Rating: {rating_info['rating']}/{rating_info['max_rating']}\n")
                    elif 'rating' in rating_info:
                        f.write(f"Rating: {rating_info['rating']}\n")
                    if 'published' in rating_info:
                        f.write(f"Published: {rating_info['published']}\n")
                    if 'updated' in rating_info:
                        f.write(f"Updated: {rating_info['updated']}\n")
                    if 'version' in rating_info:
                        f.write(f"Version: {rating_info['version']}\n")
                    if 'file_size' in rating_info:
                        f.write(f"File Size: {rating_info['file_size']}\n")
                    if 'downloads' in rating_info:
                        f.write(f"Downloads: {rating_info['downloads']:,}\n")
                    f.write("-" * 60 + "\n")
                
                f.write("DESCRIPTION:\n")
                f.write(description_text)
                
            print(f"Saved description: {description_filename}")
        except Exception as e:
            print(f"Error saving description: {e}")
        
        return True
    
    def scrape_all_expert_advisors(self, max_pages=5, start_page=1):
        """Scrape all expert advisors from multiple pages"""
        print(f"Starting to scrape MQL5 Expert Advisors (pages {start_page}-{max_pages})...")
        
        total_eas = 0
        
        for page in range(start_page, max_pages + 1):
            try:
                ea_links = self.get_expert_advisor_links(page)
                
                if not ea_links:
                    print(f"No Expert Advisors found on page {page}, stopping...")
                    break
                
                print(f"Found {len(ea_links)} Expert Advisors on page {page}")
                total_eas += len(ea_links)
                
                for i, ea in enumerate(ea_links, 1):
                    print(f"[Page {page}, Item {i}/{len(ea_links)}] Processing: {ea['title']}")
                    
                    success = self.scrape_expert_advisor_page(
                        ea['url'],
                        ea['title'],
                        ea['id']
                    )
                    
                    if success:
                        print(f"Successfully processed: {ea['title']}")
                    else:
                        print(f"Failed to process: {ea['title']}")
                
                print(f"Completed page {page}. Taking a longer break before next page...")
                time.sleep(random.uniform(10, 15))  # Longer delay between pages
                
            except KeyboardInterrupt:
                print("\nScraping interrupted by user")
                break
            except Exception as e:
                print(f"Error on page {page}: {e}")
                continue
        
        print(f"\nScraping completed! Processed {total_eas} Expert Advisors.")

def main():
    scraper = MQL5ExpertAdvisorScraper()
    
    # These parameters can be modified as needed:
    # - max_pages: How many pages to scrape (each page has ~40 EAs)
    # - start_page: Which page to start from
    
    print("MQL5 Expert Advisor Scraper")
    print("=" * 60)
    print("This will scrape Expert Advisors from https://www.mql5.com/en/code/mt5/experts")
    print("Each Expert Advisor will be saved in its own folder with:")
    print("- ZIP file containing the complete EA package")
    print("- Comprehensive text file with:")
    print("  • Full description and author information")
    print("  • User ratings, views, and metadata")
    print("  • Publication and update dates")
    print("  • File size and version information")
    print()
    
    # Configuration - Conservative settings to avoid rate limiting
    max_pages = 4  # Change this to scrape more pages (start small!)
    start_page = 1  # Change this to start from a different page
    
    print("RATE LIMITING ENABLED")
    print("This scraper includes multiple rate limiting measures:")
    print("- Random delays between 2-5 seconds per request")
    print("- Extended delays of 8-13 seconds between pages")
    print("- Progressive delays for high request counts")
    print("- Automatic retry on HTTP 429 (rate limit) responses")
    print("- Realistic browser headers to avoid detection")
    print()
    
    print(f"Scraping pages {start_page} to {max_pages} (approximately {(max_pages - start_page + 1) * 40} Expert Advisors)")
    print("Press Ctrl+C to stop at any time")
    print()
    
    scraper.scrape_all_expert_advisors(max_pages=max_pages, start_page=start_page)

if __name__ == "__main__":
    main()
