from .crawler import crawl_site
from .parser import parse_pages
from pathlib import Path
import uuid

class ScrapingJob:
    "Manages a documentation scraping job"
    def __init__(self, url, data_dir='data'):
        self.url = url.rstrip('/')  # Remove trailing slash
        self.job_id = str(uuid.uuid4())
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Set up file paths
        self.pages_file = self.data_dir / f"{self.job_id}_pages.txt"
        self.output_file = self.data_dir / f"{self.job_id}.txt"
        
        self.progress = {
            'status': 'initialized',
            'crawl_progress': 0,
            'parse_progress': 0,
            'current_url': '',
            'total_links': 0,
            'processed_links': 0
        }

    async def run(self, progress_callback=None):
        "Run the full scraping process"
        try:
            # Crawl the site
            self.progress['status'] = 'crawling'
            await crawl_site(
                self.url, 
                self.pages_file,
                self._make_crawl_callback(progress_callback)
            )

            # Parse pages
            self.progress['status'] = 'parsing'
            await parse_pages(
                self.pages_file,
                self.output_file,
                self._make_parse_callback(progress_callback)
            )

            self.progress['status'] = 'complete'
            if progress_callback:
                await progress_callback(self.progress)

            return self.output_file

        except Exception as e:
            self.progress['status'] = 'error'
            self.progress['error'] = str(e)
            if progress_callback:
                await progress_callback(self.progress)
            raise
        finally:
            # Clean up pages file after processing
            if self.pages_file.exists():
                try:
                    self.pages_file.unlink()
                except Exception as e:
                    print(f"Error cleaning up pages file: {e}")

    def _make_crawl_callback(self, main_callback):
        "Create crawler progress callback"
        async def callback(progress):
            # Update progress with crawler info
            self.progress['crawl_progress'] = progress.get('processed', 0)
            self.progress['current_url'] = progress.get('current_url', '')
            self.progress['total_links'] = progress.get('total_links', 0)
            self.progress['processed_links'] = progress.get('processed', 0)
            
            if main_callback:
                await main_callback(self.progress)
        return callback

    def _make_parse_callback(self, main_callback):
        "Create parser progress callback"
        async def callback(progress):
            # Update progress with parser info
            self.progress['parse_progress'] = progress.get('progress', 0)
            self.progress['current_url'] = progress.get('url', '')
            
            if main_callback:
                await main_callback(self.progress)
        return callback

    def cleanup(self):
        "Remove temporary files"
        try:
            if self.pages_file.exists():
                self.pages_file.unlink()
            if self.output_file.exists():
                self.output_file.unlink()
        except Exception as e:
            print(f"Error during cleanup: {e}")