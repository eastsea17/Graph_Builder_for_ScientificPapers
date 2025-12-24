
import os
import logging
import langextract as lx
from langextract.data import AnnotatedDocument, Extraction
from langextract.resolver import WordAligner
from itertools import chain
from concurrent.futures import ProcessPoolExecutor, as_completed

def process_single_document(res):
    """
    Process a single document result: Extract and Align.
    This function is run in a separate process.
    """
    try:
        # Create a fresh aligner instance for each process
        aligner = WordAligner()
        
        extractions = []
        extracted_data = res.get('extracted', {})
        
        # 1. Prepare Extractions
        if extracted_data:
            for category, items in extracted_data.items():
                if not items: continue
                class_name = category.capitalize()
                for item in items:
                    if not item: continue
                    ext = Extraction(
                        extraction_class=class_name,
                        extraction_text=item.strip()
                    )
                    extractions.append(ext)
        
        # 2. Perform Alignment
        aligned_extractions = []
        if extractions:
            try:
                aligned_groups = aligner.align_extractions(
                    extraction_groups=[extractions], 
                    source_text=res['full_text']
                )
                aligned_extractions = list(chain.from_iterable(aligned_groups))
            except Exception as e:
                # Logging in subprocess might not show up depending on config, but good to have
                # We'll just return unaligned if it fails
                aligned_extractions = extractions
        
        return AnnotatedDocument(
            document_id=res['paper_id'],
            text=res['full_text'],
            extractions=aligned_extractions
        )
    except Exception as e:
        # In case of catastrophic failure in the worker
        # Return a minimal valid document or re-raise
        # Returning minimal doc to match expected interface
        return AnnotatedDocument(
            document_id=res.get('paper_id', 'unknown'),
            text=res.get('full_text', ''),
            extractions=[]
        )

class Visualizer:
    def __init__(self, config):
        self.output_dir = config['output_dir']
        # Aligner is now instantiated inside the worker process

    def create_visualization(self, results):
        """
        Generates visualization using langextract library.
        :param results: List of extracted data dictionaries.
        """
        try:
            # Prepare output paths
            jsonl_name = "extraction_results.jsonl"
            jsonl_path = os.path.join(self.output_dir, jsonl_name)
            html_path = os.path.join(self.output_dir, "graph_visualization.html") 
            
            # Convert results to LangExtract AnnotatedDocument objects
            input_docs = []
            from tqdm import tqdm
            # [Modified] Multiprocessing for Alignment
            logging.info(f"Aligning {len(results)} documents using Multiprocessing...")
            
            with ProcessPoolExecutor() as executor:
                # Submit all tasks
                future_to_doc = {executor.submit(process_single_document, res): res for res in results}
                
                for future in tqdm(as_completed(future_to_doc), total=len(results), desc="Processing & Aligning"):
                    try:
                        doc = future.result()
                        input_docs.append(doc)
                    except Exception as e:
                        logging.error(f"Error processing document: {e}")
            
            # [Added] Sort documents by ID (e.g., Paper_1, Paper_2, Paper_10)
            def get_sort_key(doc):
                try:
                    # Assumes format "Paper_123"
                    return int(str(doc.document_id).split('_')[-1])
                except (ValueError, IndexError):
                    return str(doc.document_id)
            
            input_docs.sort(key=get_sort_key)

            # Save the results to a JSONL file
            logging.info(f"Saving {len(input_docs)} annotated documents to {jsonl_path}...")
            lx.io.save_annotated_documents(input_docs, output_name=jsonl_name, output_dir=self.output_dir)

            # Generate visualization pages for ALL documents
            logging.info("Generating visualization pages for all documents...")
            pages_dir = os.path.join(self.output_dir, "pages")
            os.makedirs(pages_dir, exist_ok=True)
            
            paper_map = [] # stores id, label (truncated text), and filename
            
            from tqdm import tqdm
            for i, doc in enumerate(tqdm(input_docs, desc="Generating HTMLs")):
                try:
                    # lx.visualize can take a single AnnotatedDocument
                    # We accept the returned HTML string or object
                    html_obj = lx.visualize(doc) 
                    html_str = html_obj.data if hasattr(html_obj, 'data') else str(html_obj)
                    
                    filename = f"doc_{i}.html"
                    file_path = os.path.join(pages_dir, filename)
                    
                    with open(file_path, "w") as f:
                        f.write(html_str)
                        
                    # Create a label for the menu
                    label = doc.document_id
                    if doc.text:
                        preview = doc.text[:50] + "..." if len(doc.text) > 50 else doc.text
                        label = f"{doc.document_id}: {preview}"
                        
                    paper_map.append({
                        "id": doc.document_id,
                        "label": label,
                        "file": f"pages/{filename}"
                    })
                except Exception as e:
                    logging.warning(f"Failed to visualize doc {doc.document_id}: {e}")

            # Create the main index file (the Multi-Document Player)
            index_html_path = os.path.join(self.output_dir, "graph_visualization.html")
            
            # Generate the Index HTML content
            import json
            papers_json = json.dumps(paper_map)
            
            index_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research Papers Visualization</title>
    <style>
        body {{ margin: 0; padding: 0; font-family: sans-serif; display: flex; height: 100vh; overflow: hidden; }}
        #sidebar {{
            width: 300px;
            background: #f5f5f5;
            border-right: 1px solid #ddd;
            display: flex;
            flex-direction: column;
            height: 100%;
        }}
        #header {{
            padding: 15px;
            background: #fff;
            border-bottom: 1px solid #eee;
            font-weight: bold;
        }}
        #paper-list {{
            flex: 1;
            overflow-y: auto;
            padding: 0;
            margin: 0;
            list-style: none;
        }}
        .paper-item {{
            padding: 10px 15px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            font-size: 13px;
        }}
        .paper-item:hover {{ background: #e3f2fd; }}
        .paper-item.active {{ background: #2196f3; color: white; }}
        #content {{ flex: 1; height: 100%; }}
        iframe {{ width: 100%; height: 100%; border: none; }}
        .search-box {{ padding: 10px; border-bottom: 1px solid #eee; }}
        .search-box input {{ width: 95%; padding: 5px; }}
    </style>
</head>
<body>
    <div id="sidebar">
        <div id="header">Paper Navigator ({len(paper_map)})</div>
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search papers..." onkeyup="filterPapers()">
        </div>
        <ul id="paper-list"></ul>
    </div>
    <div id="content">
        <iframe id="docFrame" name="docFrame" src=""></iframe>
    </div>

    <script>
        const papers = {papers_json};
        const listEl = document.getElementById('paper-list');
        const frame = document.getElementById('docFrame');
        let activeItem = null;

        function renderList(items) {{
            listEl.innerHTML = '';
            items.forEach((p, idx) => {{
                const li = document.createElement('li');
                li.className = 'paper-item';
                li.textContent = p.label;
                li.onclick = () => loadPaper(p, li);
                listEl.appendChild(li);
                
                // Auto load first item
                if (idx === 0 && !frame.src) {{
                    loadPaper(p, li);
                }}
            }});
        }}

        function loadPaper(paper, liElement) {{
            frame.src = paper.file;
            if (activeItem) activeItem.classList.remove('active');
            liElement.classList.add('active');
            activeItem = liElement;
        }}

        function filterPapers() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const filtered = papers.filter(p => p.label.toLowerCase().includes(query));
            renderList(filtered);
        }}

        // Initial render
        renderList(papers);
    </script>
</body>
</html>
            """
            
            with open(index_html_path, "w") as f:
                f.write(index_content)
            
            print(f"Multi-document visualization created at {index_html_path}")
            
        except ImportError:
            logging.error("langextract library not found. Please install it with `pip install langextract`.")
        except Exception as e:
            logging.error(f"Error creating visualization with langextract: {e}")
            logging.debug("Full error:", exc_info=True)
