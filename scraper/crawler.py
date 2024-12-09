import re
import requests
from bs4 import BeautifulSoup
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin, urldefrag
from pathlib import Path

# Regex for URL validation
HTTP_URL_PATTERN = r'^http[s]*://.+'

class HyperlinkParser(HTMLParser):
    "HTML parser that extracts hyperlinks from a page"
    def __init__(self):
        super().__init__()
        self.hyperlinks = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "href" in attrs:
            self.hyperlinks.append(attrs["href"])

def get_hyperlinks(url, session):
    try:
        response = session.get(url, timeout=10)
        final_url = response.url
        if not response.headers['Content-Type'].startswith("text/html"):
            return [], final_url
        parser = HyperlinkParser()
        parser.feed(response.text)
        return parser.hyperlinks, final_url
    except Exception as e:
        print(f"Error fetching {url}:", e)
        return [], url

def get_domain_hyperlinks(local_domain, base_url, url, session):
    clean_links = []
    hyperlinks, final_url = get_hyperlinks(url, session)
    
    # Your existing efficient link processing code
    for link in set(hyperlinks):  # Using set() to deduplicate immediately
        clean_link = None
        if re.search(HTTP_URL_PATTERN, link):
            url_obj = urlparse(link)
            if url_obj.netloc == local_domain:
                clean_link = urldefrag(link)[0]
        else:
            if link.startswith(('/','./')) or not link.startswith(('#','mailto:')):
                link = urljoin(final_url, link)
                url_obj = urlparse(link)
                if url_obj.netloc == local_domain:
                    clean_link = urldefrag(link)[0]
                    
        if clean_link and 'cdn-cgi' not in clean_link:
            if not clean_link.endswith(('.md','.html.md')):
                clean_links.append(clean_link)
            
    return list(set(clean_links))

def grab_urls(url):
    session = requests.Session()  # Use session for connection pooling
    local_domain = urlparse(url).netloc
    queue = deque([url])
    seen = set([urldefrag(url)[0]])
    all_links = [url]

    while queue:
        url = queue.popleft()
        print(url)

        new_links = get_domain_hyperlinks(local_domain, url, url, session)
        new_links.sort()
        
        for link in new_links:
            if link not in seen:
                queue.append(link)
                seen.add(link)
                all_links.append(link)

    sorted_links = [all_links[0]] + sorted(all_links[1:])
    return sorted_links

async def crawl_site(url, output_file, progress_callback=None):
    "Crawl site and save URLs to file"
    domain = urlparse(url).netloc
    queue = deque([url])
    seen = set([urldefrag(url)[0]])
    links = [url]
    total_processed = 0

    while queue:
        url = queue.popleft()
        total_processed += 1
        
        if progress_callback:
            await progress_callback({
                'status': 'crawling',
                'current_url': url,
                'processed': total_processed
            })

        new_links = get_domain_links(domain, url, url)
        new_links.sort()
        
        for link in new_links:
            if link not in seen:
                queue.append(link)
                seen.add(link)
                links.append(link)

    # Keep homepage first, sort rest
    sorted_links = [links[0]] + sorted(links[1:])
    
    # Write to file
    output_file = Path(output_file)
    output_file.parent.mkdir(exist_ok=True)
    output_file.write_text('\n'.join(sorted_links), encoding='utf-8')
    
    if progress_callback:
        await progress_callback({
            'status': 'complete',
            'total_links': len(sorted_links)
        })

    return sorted_links