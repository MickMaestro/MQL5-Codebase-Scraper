import requests
from bs4 import BeautifulSoup
import os
import re
import time
import random
from urllib.parse import urljoin, urlparse
import zipfile
from pathlib import Path

class MQL5LibraryScraper:
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
    
    def get_library_links(self, page=1):
        """Get all library links from a specific page"""
        url = f"{self.base_url}/en/code/mt5/libraries"
        if page > 1:
            url += f"/page{page}"
            
        print(f"Fetching page {page}...")
        response = self.safe_request(url, is_page_request=True)
        
        if not response or response.status_code != 200:
            print(f"Failed to get page {page}: status {response.status_code if response else 'No response'}")
            return []
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all library links
        library_links = []
        links = soup.find_all('a', href=re.compile(r'/en/code/\d+$'))
        
        for link in links:
            href = link.get('href')
            title = link.get_text(strip=True)
            if href and title:
                full_url = urljoin(self.base_url, href)
                library_links.append({
                    'url': full_url,
                    'title': title,
                    'id': href.split('/')[-1]
                })
        
        return library_links
    
    def extract_description_and_rating(self, soup):
        """Extract description text, author name, and comprehensive rating information"""
        description_text = ""
        author_name = ""
        rating_info = {}
        
        # Convert soup to text to work with string patterns
        page_text = soup.get_text()
        
        # Extract author name - try multiple patterns
        author_patterns = [
            r'Author:\s*([^\n\r]+)',
            r'by\s+([^\n\r,]+)',
            r'Created\s+by\s*:?\s*([^\n\r,]+)',
            r'Developer:\s*([^\n\r]+)',
            r'Publisher:\s*([^\n\r]+)'
        ]
        
        for pattern in author_patterns:
            author_match = re.search(pattern, page_text, re.IGNORECASE)
            if author_match:
                author_name = author_match.group(1).strip()
                # Clean up author name
                author_name = re.sub(r'\s+', ' ', author_name)
                if len(author_name) > 2 and not author_name.isdigit():
                    break
        
        # Try to find author in HTML structure
        if not author_name:
            author_elements = soup.find_all(['span', 'div', 'a'], string=re.compile(r'Author|by|Created', re.IGNORECASE))
            for element in author_elements:
                parent = element.parent or element
                next_sibling = element.find_next_sibling()
                if next_sibling:
                    potential_author = next_sibling.get_text(strip=True)
                    if potential_author and len(potential_author) > 2 and not potential_author.isdigit():
                        author_name = potential_author
                        break
        
        # Extract comprehensive description
        description_sections = []
        
        # Method 1: Look for main description content
        description_divs = soup.find_all(['div', 'section'], class_=re.compile(r'description|content|summary|details', re.IGNORECASE))
        for div in description_divs:
            text = div.get_text(strip=True)
            if text and len(text) > 50:
                description_sections.append(text)
        
        # Method 2: Look for paragraphs with substantial content
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text(strip=True)
            if text and len(text) > 30 and not re.match(r'^(Go to|Download|View|Rating|Published)', text, re.IGNORECASE):
                description_sections.append(text)
        
        # Method 3: Try meta description as fallback
        if not description_sections:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                description_sections.append(meta_desc.get('content'))
        
        # Method 4: Extract text between common markers if other methods fail
        if not description_sections:
            freelance_pattern = r'Go to Freelance.*?(?=Go to Discussion|Download|Rating|$)'
            match = re.search(freelance_pattern, page_text, re.DOTALL | re.IGNORECASE)
            
            if match:
                description_section = match.group(0)
                lines = description_section.split('\n')
                meaningful_lines = []
                
                for line in lines:
                    line = line.strip()
                    if (line and 
                        not line.startswith('Go to') and 
                        'Freelance' not in line and
                        len(line) > 10 and
                        not line.isdigit()):
                        meaningful_lines.append(line)
                
                if meaningful_lines:
                    description_sections.append('\n'.join(meaningful_lines))
        
        # Combine and clean description
        if description_sections:
            # Remove duplicates and clean
            unique_sections = []
            for section in description_sections:
                cleaned = re.sub(r'\s+', ' ', section.strip())
                if cleaned not in unique_sections and len(cleaned) > 20:
                    unique_sections.append(cleaned)
            
            description_text = '\n\n'.join(unique_sections[:3])  # Limit to top 3 sections
        
        # Fallback if still no description
        if not description_text:
            description_text = "No detailed description available."
        
        # Extract comprehensive rating and metadata information
        try:
            # Look for views with multiple patterns
            views_patterns = [
                r'Views?:\s*(\d+(?:,\d+)*)',
                r'(\d+(?:,\d+)*)\s*views?',
                r'Viewed\s*(\d+(?:,\d+)*)\s*times?'
            ]
            
            for pattern in views_patterns:
                views_match = re.search(pattern, page_text, re.IGNORECASE)
                if views_match:
                    views_str = views_match.group(1).replace(',', '')
                    rating_info['views'] = int(views_str)
                    break
            
            # Look for rating with expanded patterns
            rating_patterns = [
                r'Rating:\s*\((\d+(?:\.\d+)?)\s*out\s*of\s*(\d+)\)',
                r'(\d+(?:\.\d+)?)\s*out\s*of\s*(\d+)',
                r'Rating:\s*(\d+(?:\.\d+)?)/(\d+)',
                r'★+\s*(\d+(?:\.\d+)?)/(\d+)',
                r'(\d+(?:\.\d+)?)\s*stars?',
                r'Score:\s*(\d+(?:\.\d+)?)',
                r'Rate:\s*(\d+(?:\.\d+)?)'
            ]
            
            for pattern in rating_patterns:
                rating_match = re.search(pattern, page_text, re.IGNORECASE)
                if rating_match:
                    rating_info['rating'] = float(rating_match.group(1))
                    if len(rating_match.groups()) > 1:
                        rating_info['max_rating'] = int(rating_match.group(2))
                    break
            
            # Look for publish/creation date with expanded patterns
            date_patterns = [
                r'Published:\s*(\d{1,2}[\s\/\.-]\w+[\s\/\.-]\d{4})',
                r'Created:\s*(\d{1,2}[\s\/\.-]\w+[\s\/\.-]\d{4})',
                r'Date:\s*(\d{1,2}[\s\/\.-]\w+[\s\/\.-]\d{4})',
                r'(\d{1,2}\s+\w+\s+\d{4})',
                r'(\w+\s+\d{1,2},?\s+\d{4})',
                r'(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})'
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, page_text, re.IGNORECASE)
                if date_match:
                    rating_info['published'] = date_match.group(1)
                    break
            
            # Look for download count with expanded patterns
            downloads_patterns = [
                r'Downloads?:\s*(\d+(?:,\d+)*)',
                r'Downloaded\s*(\d+(?:,\d+)*)\s*times?',
                r'(\d+(?:,\d+)*)\s*downloads?'
            ]
            
            for pattern in downloads_patterns:
                downloads_match = re.search(pattern, page_text, re.IGNORECASE)
                if downloads_match:
                    downloads_str = downloads_match.group(1).replace(',', '')
                    rating_info['downloads'] = int(downloads_str)
                    break
            
            # Look for additional metrics
            favorites_match = re.search(r'Favorites?:\s*(\d+)', page_text, re.IGNORECASE)
            if favorites_match:
                rating_info['favorites'] = int(favorites_match.group(1))
            
            comments_match = re.search(r'Comments?:\s*(\d+)', page_text, re.IGNORECASE)
            if comments_match:
                rating_info['comments'] = int(comments_match.group(1))
            
            # Look for version information
            version_match = re.search(r'Version:\s*([\d\.]+)', page_text, re.IGNORECASE)
            if version_match:
                rating_info['version'] = version_match.group(1)
            
            # Look for file size
            size_match = re.search(r'Size:\s*([\d\.]+\s*[KMG]?B)', page_text, re.IGNORECASE)
            if size_match:
                rating_info['file_size'] = size_match.group(1)
                
        except Exception as e:
            print(f"Error extracting rating info: {e}")
        
        return description_text, author_name, rating_info
    
    def scrape_library_page(self, library_url, library_title, library_id):
        """Scrape individual library page for zip file, source files, and description"""
        print(f"Scraping library: {library_title}")
        
        response = self.safe_request(library_url)
        if not response or response.status_code != 200:
            print(f"Failed to get library page: {response.status_code if response else 'No response'}")
            return False
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Create folder for this library in the script directory
        folder_name = self.clean_filename(library_title)
        folder_path = os.path.join(self.script_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # Find download links for ZIP files
        zip_download_link = None
        zip_links = soup.find_all('a', href=re.compile(r'/en/code/download/\d+\.zip'))
        if zip_links:
            zip_download_link = urljoin(self.base_url, zip_links[0].get('href'))
        
        # Find download links for source files (.mq5, .mq4, .mqh, .txt, etc.)
        source_links = []
        source_file_links = soup.find_all('a', href=re.compile(r'/en/code/download/\d+/[^/]+\.(mq5|mq4|mqh|txt|ex5|ex4)$'))
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
                    if source['filename'].endswith(('.txt', '.mq5', '.mq4', '.mqh')):
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
        
        # Extract description, author, and rating information
        description_text, author_name, rating_info = self.extract_description_and_rating(soup)
        
        if not description_text:
            description_text = f"No detailed description found for {library_title} (ID: {library_id})\nURL: {library_url}"
        
        # Clean up the description text
        description_text = re.sub(r'\s+', ' ', description_text)  # Normalize whitespace
        description_text = description_text.strip()
        
        # Save complete information to text file named after the library
        info_filename = os.path.join(folder_path, f"{folder_name}.txt")
        try:
            with open(info_filename, 'w', encoding='utf-8') as f:
                f.write(f"LIBRARY INFORMATION\n")
                f.write("=" * 50 + "\n")
                f.write(f"Library Name: {library_title}\n")
                f.write(f"Library ID: {library_id}\n")
                f.write(f"URL: {library_url}\n")
                
                # Add author information
                if author_name:
                    f.write(f"Author: {author_name}\n")
                else:
                    f.write("Author: Not specified\n")
                
                f.write("\n" + "=" * 50 + "\n")
                
                # Add comprehensive rating and metadata information
                if rating_info:
                    f.write("RATINGS & STATISTICS\n")
                    f.write("-" * 30 + "\n")
                    
                    if 'rating' in rating_info:
                        if 'max_rating' in rating_info:
                            f.write(f"Rating: {rating_info['rating']}/{rating_info['max_rating']}\n")
                        else:
                            f.write(f"Rating: {rating_info['rating']}\n")
                    
                    if 'views' in rating_info:
                        f.write(f"Views: {rating_info['views']:,}\n")
                    
                    if 'downloads' in rating_info:
                        f.write(f"Downloads: {rating_info['downloads']:,}\n")
                    
                    if 'favorites' in rating_info:
                        f.write(f"Favorites: {rating_info['favorites']}\n")
                    
                    if 'comments' in rating_info:
                        f.write(f"Comments: {rating_info['comments']}\n")
                    
                    if 'published' in rating_info:
                        f.write(f"Published: {rating_info['published']}\n")
                    
                    if 'version' in rating_info:
                        f.write(f"Version: {rating_info['version']}\n")
                    
                    if 'file_size' in rating_info:
                        f.write(f"File Size: {rating_info['file_size']}\n")
                    
                    f.write("\n" + "=" * 50 + "\n")
                
                # Add complete description
                f.write("LIBRARY DESCRIPTION\n")
                f.write("-" * 30 + "\n")
                f.write(description_text)
                f.write("\n\n" + "=" * 50 + "\n")
                f.write(f"Data extracted on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                
            print(f"Saved complete library information: {info_filename}")
        except Exception as e:
            print(f"Error saving library information: {e}")
        
        return True
    
    def scrape_all_libraries(self, max_pages=5, start_page=1):
        """Scrape all libraries from multiple pages"""
        print(f"Starting to scrape MQL5 libraries (pages {start_page}-{max_pages})...")
        
        total_libraries = 0
        
        for page in range(start_page, max_pages + 1):
            try:
                library_links = self.get_library_links(page)
                
                if not library_links:
                    print(f"No libraries found on page {page}, stopping...")
                    break
                
                print(f"Found {len(library_links)} libraries on page {page}")
                total_libraries += len(library_links)
                
                for i, library in enumerate(library_links, 1):
                    print(f"[Page {page}, Item {i}/{len(library_links)}] Processing: {library['title']}")
                    
                    success = self.scrape_library_page(
                        library['url'],
                        library['title'],
                        library['id']
                    )
                    
                    if success:
                        print(f"Successfully processed: {library['title']}")
                    else:
                        print(f"Failed to process: {library['title']}")
                
                print(f"Completed page {page}. Taking a longer break before next page...")
                time.sleep(random.uniform(10, 15))  # Longer delay between pages
                
            except KeyboardInterrupt:
                print("\nScraping interrupted by user")
                break
            except Exception as e:
                print(f"Error on page {page}: {e}")
                continue
        
        print(f"\nScraping completed! Processed {total_libraries} libraries.")

def main():
    scraper = MQL5LibraryScraper()
    
    # These parameters can be modified as needed:
    # - max_pages: How many pages to scrape (each page has ~40 libraries)
    # - start_page: Which page to start from
    
    print("MQL5 Library Scraper")
    print("=" * 50)
    print("This will scrape libraries from https://www.mql5.com/en/code/mt5/libraries")
    print("Each library will be saved in its own folder with:")
    print("- ZIP file containing the library archive")
    print("- Individual source files (.mq5, .mq4, .mqh, .txt, etc.)")
    print("- Text file with library description and user ratings")
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
    
    print(f"Scraping pages {start_page} to {max_pages} (approximately {(max_pages - start_page + 1) * 40} libraries)")
    print("Press Ctrl+C to stop at any time")
    print()
    
    scraper.scrape_all_libraries(max_pages=max_pages, start_page=start_page)

if __name__ == "__main__":
    main()
