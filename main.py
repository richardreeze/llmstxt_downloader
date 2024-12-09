from fasthtml.common import *
from scraper import ScrapingJob

# Setup headers with TailwindCSS and DaisyUI
hdrs = (
    Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/@tailwindcss/typography/dist/typography.min.css"),
    Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@latest/dist/full.css"),
    Script(src="https://cdn.tailwindcss.com")
)

# Initialize FastHTML app with headers and websocket support
app, rt = fast_app(hdrs=hdrs, exts='ws')
jobs = {}

@rt('/')
def get():
    return Titled("llms.txt Scraper",
        Main(
            Div(
                H1("llms.txt Scraper", cls="text-3xl font-bold mb-4"),
                P("Enter a URL to scrape documentation into a single llms.txt file", 
                  cls="text-gray-600 mb-6"),
                Form(
                    Div(
                        Input(type="url", name="url", 
                              placeholder="Enter documentation URL (e.g., https://docs.fastht.ml/)",
                              cls="input input-bordered w-full mb-2",
                              required=True),
                        Button("Start Scraping", cls="btn btn-primary w-full"),
                        cls="form-control"
                    ),
                    hx_post="/scrape",
                    hx_target="#result",
                    hx_disable_element="#submit-btn"
                ),
                Div(id="result", cls="mt-4"),
                cls="container mx-auto max-w-2xl p-4"
            ),
            cls="prose max-w-none"
        )
    )

@rt('/scrape')
async def post(url: str, session):
    try:
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            return Div("Please enter a valid URL starting with http:// or https://",
                      cls="alert alert-error")
        
        # Create new scraping job
        job = ScrapingJob(url)
        jobs[job.job_id] = job
        session['job_id'] = job.job_id
        
        # Return progress monitoring div
        return Div(
            Div(
                P("Starting scraper...", cls="text-lg"),
                Progress(cls="progress progress-primary w-full"),
                id="progress",
                cls="card bg-base-200 p-4"
            ),
            hx_ext="sse",
            sse_connect=f"/status/{job.job_id}",
            sse_swap="message"
        )
    except Exception as e:
        return Div(f"Error starting scraper: {str(e)}", cls="alert alert-error")

async def progress_handler(progress):
    """Convert progress updates to user-friendly messages"""
    status = progress['status']
    stats_div = None
    
    if status == 'crawling':
        current = progress.get('current_url', '')
        processed = progress.get('processed_links', 0)
        total = progress.get('total_links', 0)
        msg = Div(
            H3("Phase 1: Discovering Pages", cls="font-bold mb-2"),
            P(f"Currently scanning: {current}", cls="text-sm mb-1"),
            P(f"Pages found so far: {processed}", cls="text-sm"),
            cls="space-y-1"
        )
        prog = processed * 5  # Estimate progress for crawling phase
        
    elif status == 'parsing':
        current_progress = progress.get('progress', 0)
        current_url = progress.get('current_url', '')
        current = progress.get('current', 0)
        total = progress.get('total', 0)
        msg = Div(
            H3("Phase 2: Converting Pages", cls="font-bold mb-2"),
            P(f"Processing page {current} of {total}", cls="text-sm mb-1"),
            P(f"Current page: {current_url}", cls="text-sm mb-1"),
            P(f"Overall progress: {current_progress:.1f}%", cls="text-sm"),
            cls="space-y-1"
        )
        prog = current_progress
        
    elif status == 'complete':
        total_pages = progress.get('pages', 0)
        msg = Div(
            H3("Processing Complete!", cls="font-bold text-success mb-2"),
            P(f"Successfully processed {total_pages} pages.", cls="text-sm"),
            P("Your documentation is ready for download.", cls="text-sm"),
            cls="space-y-1"
        )
        prog = 100
        
    elif status == 'error':
        error_msg = progress.get('error', 'Unknown error occurred')
        msg = Div(
            H3("Error Occurred", cls="font-bold text-error mb-2"),
            P(error_msg, cls="text-sm"),
            cls="space-y-1"
        )
        prog = 0
    
    return Div(
        msg,
        Progress(
            value=prog, 
            max=100, 
            cls=f"progress w-full mt-4 " + 
                ("progress-error" if status == 'error' else "progress-primary")
        ),
        Div(
            A("Download docs.txt", 
              href=f"/download/{progress.get('job_id')}", 
              cls="btn btn-success"
            ) if status == 'complete' else None,
            A("Start Over", 
              href="/",
              cls="btn btn-ghost ml-2"
            ) if status in ['complete', 'error'] else None,
            cls="mt-4 flex gap-2"
        ),
        cls="card bg-base-200 p-4"
    )

@rt("/status/{job_id}")
async def get(job_id: str):
    if job_id not in jobs:
        return Div("Job not found", cls="alert alert-error")
        
    async def status_updates():
        job = jobs[job_id]
        
        async def callback(progress):
            progress['job_id'] = job_id
            yield sse_message(await progress_handler(progress))
        
        try:
            await job.run(callback)
        except Exception as e:
            yield sse_message(
                await progress_handler({
                    'status': 'error',
                    'error': str(e),
                    'job_id': job_id
                })
            )
    
    return EventStream(status_updates())

@rt("/download/{job_id}")
async def get(job_id: str):
    if job_id not in jobs:
        return Div("Job not found", cls="alert alert-error")
        
    try:
        job = jobs[job_id]
        response = FileResponse(
            job.output_file,
            filename="docs.txt",
            media_type="text/plain"
        )
        
        # Clean up after sending file
        job.cleanup()
        jobs.pop(job_id, None)
        
        return response
    except Exception as e:
        return Div(f"Error downloading file: {str(e)}", cls="alert alert-error")

if __name__ == "__main__":
    serve()