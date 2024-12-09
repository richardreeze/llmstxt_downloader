import requests
from bs4 import BeautifulSoup
import re
import html2text
from pathlib import Path

def find_main_content(soup):
    "Find largest text block likely to be main content"
    blocks = []
    for elem in soup.find_all(['div', 'section', 'article']):
        # Skip navigation/footer elements
        if any(cls in str(elem.get('class', [])).lower() 
               for cls in ['nav', 'footer', 'header', 'sidebar', 'menu']):
            continue
        txt_len = len(elem.get_text(strip=True))
        blocks.append((txt_len, elem))
    return max(blocks, key=lambda x: x[0])[1] if blocks else None

def clean_element(elem):
    "Remove unwanted elements and classes"
    # Remove unwanted tags
    for tag in elem.find_all(['script', 'style', 'nav', 'header', 'footer', 
                            'aside', 'meta', 'noscript']):
        tag.decompose()

    # Remove elements with unwanted classes
    unwanted = [
        'nav', 'menu', 'header', 'footer', 'sidebar', 'ad', 'social', 
        'comments', 'related', 'share', 'meta', 'tags', 'toolbar',
        'cookie', 'popup', 'overlay', 'newsletter', 'banner'
    ]
    for cls in unwanted:
        for tag in elem.find_all(class_=re.compile(cls, re.I)):
            tag.decompose()

    return elem

async def parse_pages(urls_file, output_file, progress_callback=None):
    "Parse URLs from file and convert to markdown"
    try:
        urls = Path(urls_file).read_text(encoding='UTF-8').splitlines()
        total = len(urls)
        content = []
        session = requests.Session()  # Use session for connection pooling
        
        # Configure markdown converter
        h = html2text.HTML2Text()
        h.body_width = 0  # Don't wrap text
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_tables = False
        h.ignore_emphasis = False
        h.mark_code = True
        
        for idx, url in enumerate(urls, 1):
            try:
                if progress_callback:
                    await progress_callback({
                        'status': 'parsing',
                        'url': url,
                        'progress': round((idx / total) * 100, 2),
                        'current': idx,
                        'total': total
                    })

                # Get page content with timeout
                resp = session.get(
                    url, 
                    timeout=30,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    }
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                # Try to find main content using various selectors
                main = None
                selectors = [
                    'main', 'article', '[role="main"]', '.main-content', 
                    '#main-content', '.post-content', '.article-content', 
                    '.content', '#content', '.entry-content', '.post', 
                    '.article-body', '.page-content', '.document-content'
                ]

                for sel in selectors:
                    if sel.startswith('.'):
                        main = soup.find(class_=sel[1:])
                    elif sel.startswith('#'):
                        main = soup.find(id=sel[1:])
                    elif sel.startswith('['):
                        attr, val = sel[1:-1].split('=')
                        main = soup.find(attrs={attr: val.strip('"')})
                    else:
                        main = soup.find(sel)
                    if main: break

                # Fallback to largest text block if no main content found
                if not main:
                    main = find_main_content(soup)
                if not main:
                    main = soup.body

                if main:
                    # Clean up the content
                    main = clean_element(main)
                    
                    # Convert to markdown
                    md = h.handle(str(main))
                    
                    # Clean up markdown
                    md = re.sub(r'\n\s*\n', '\n\n', md)  # Multiple blank lines
                    md = '\n'.join(line.rstrip() for line in md.splitlines())  # Trailing space
                    md = '\n'.join(line for line in md.splitlines() 
                        if not re.match(r'^[\s\-_=*#]+$', line))  # Symbol-only lines
                    md = re.sub(r'\[\]\(.*?\)', '', md)  # Empty links
                    md = re.sub(r' +', ' ', md)  # Multiple spaces
                    md = re.sub(r'\n{3,}', '\n\n', md)  # Excessive newlines
                    
                    # Add source comment and separator
                    content.append(f"<!-- Source: {url} -->\n\n{md}\n\n---")
                else:
                    print(f"No content found for {url}")

            except Exception as e:
                print(f"Failed to parse {url}: {e}")
                content.append(f"<!-- Failed to parse {url}: {str(e)} -->\n\n---")
                continue

        # Write final output
        Path(output_file).write_text('\n\n'.join(content), encoding='UTF-8')
        
        if progress_callback:
            await progress_callback({
                'status': 'complete',
                'pages': len(content),
                'progress': 100
            })

        return content

    except Exception as e:
        print(f"Failed to process pages: {e}")
        raise