import os
import logging
import json
import langextract as lx
from langextract.data import AnnotatedDocument, Extraction
from langextract.resolver import WordAligner
from itertools import chain
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

# process_single_document 함수는 기존과 동일하게 유지
def process_single_document(res):
    """
    Multiprocessing worker function.
    Reads a result dict, initializes a local WordAligner, and returns AnnotatedDocument.
    """
    try:
        # Initialize aligner here (per process)
        aligner = WordAligner()
        
        extractions = []
        extracted_data = res.get('extracted', {})
        
        # Convert dict to Extraction objects
        if extracted_data:
            for category, items in extracted_data.items():
                if not items: continue
                # Capitalize category name (background -> Background)
                class_name = category.capitalize()
                for item in items:
                    if not item: continue
                    ext = Extraction(extraction_class=class_name, extraction_text=item.strip())
                    extractions.append(ext)
        
        # Perform alignment
        aligned_extractions = []
        if extractions:
            try:
                # Need to wrap extractions in a list of lists as align_extractions expects groups
                aligned_groups = aligner.align_extractions(
                    extraction_groups=[extractions], 
                    source_text=res['full_text']
                )
                # Flatten the result
                aligned_extractions = list(chain.from_iterable(aligned_groups))
            except Exception as e:
                logging.warning(f"Alignment failed for doc {res.get('paper_id')}: {e}")
                # Fallback to unaligned extractions if alignment fails
                aligned_extractions = extractions
        
        return AnnotatedDocument(
            document_id=res['paper_id'],
            text=res['full_text'],
            extractions=aligned_extractions
        )
    except Exception as e:
        logging.error(f"Error processing document {res.get('paper_id', 'unknown')}: {e}")
        return AnnotatedDocument(document_id=res.get('paper_id','unknown'), text='', extractions=[])

class Visualizer:
    def __init__(self, config):
        self.output_dir = config['output_dir']

    def create_visualization(self, results):
        """
        Generates a SINGLE HTML file containing all visualizations.
        """
        try:
            # 출력 경로 설정 (단일 파일)
            output_file_name = "graph_visualization_all_in_one.html"
            output_path = os.path.join(self.output_dir, output_file_name)
            
            # [Step 1] 문서 정렬 및 처리 (기존 로직 유지)
            input_docs = []
            logging.info(f"Aligning {len(results)} documents with multiprocessing...")
            
            # Use ProcessPoolExecutor for parallel processing
            with ProcessPoolExecutor() as executor:
                future_to_doc = {executor.submit(process_single_document, res): res for res in results}
                
                for future in tqdm(as_completed(future_to_doc), total=len(results), desc="Processing & Aligning"):
                    try:
                        doc = future.result()
                        input_docs.append(doc)
                    except Exception as e:
                        logging.error(f"Worker exception: {e}")
            
            # Sort documents by ID (Paper_1, Paper_2, ...)
            def get_sort_key(doc):
                try:
                    return int(str(doc.document_id).split('_')[-1])
                except:
                    return str(doc.document_id)
            input_docs.sort(key=get_sort_key)

            # [Step 2] 각 문서의 HTML 문자열을 메모리에 수집 (파일 저장 X)
            logging.info("Generating HTML strings for integration...")
            paper_data = [] 
            
            for doc in tqdm(input_docs, desc="Rendering HTMLs"):
                try:
                    # 시각화 HTML 생성
                    html_obj = lx.visualize(doc) 
                    html_content = html_obj.data if hasattr(html_obj, 'data') else str(html_obj)
                    
                    # 리스트 라벨 생성
                    label = doc.document_id
                    if doc.text:
                        preview = doc.text[:50] + "..." if len(doc.text) > 50 else doc.text
                        label = f"{doc.document_id}: {preview}"
                        
                    paper_data.append({
                        "id": doc.document_id,
                        "label": label,
                        "content": html_content  # [핵심] HTML 내용을 통째로 저장
                    })
                except Exception as e:
                    logging.warning(f"Failed to visualize {doc.document_id}: {e}")

            # [Step 3] 단일 HTML 파일 생성 (JSON 데이터 내장)
            # Python 객체를 JSON 문자열로 변환 (JS에서 사용)
            papers_json_str = json.dumps(paper_data)
            
            # [CRITICAL FIX] HTML 내에 JSON을 삽입할 때, </script> 등의 태그가 포함되어 있으면
            # 브라우저가 스크립트 종료로 오인하여 페이지가 깨집니다.
            # 따라서 '<' 문자를 유니코드 이스케이프(\u003c)로 변환하여 안전하게 만듭니다.
            papers_json_str = papers_json_str.replace('<', '\\u003c')
            
            single_html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research Papers Visualization (All-in-One)</title>
    <style>
        body {{ margin: 0; padding: 0; font-family: sans-serif; display: flex; height: 100vh; overflow: hidden; }}
        #sidebar {{ width: 300px; background: #f5f5f5; border-right: 1px solid #ddd; display: flex; flex-direction: column; height: 100%; }}
        #header {{ padding: 15px; background: #fff; border-bottom: 1px solid #eee; font-weight: bold; }}
        #paper-list {{ flex: 1; overflow-y: auto; padding: 0; margin: 0; list-style: none; }}
        .paper-item {{ padding: 10px 15px; border-bottom: 1px solid #eee; cursor: pointer; font-size: 13px; }}
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
        <div id="header">Paper Navigator ({len(paper_data)})</div>
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search papers..." onkeyup="filterPapers()">
        </div>
        <ul id="paper-list"></ul>
    </div>
    <div id="content">
        <iframe id="docFrame" name="docFrame"></iframe>
    </div>

    <script>
        // 전체 데이터를 JS 변수로 들고 있음 (메모리 사용량 증가 주의)
        const papers = {papers_json_str};
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
                
                if (idx === 0) loadPaper(p, li);
            }});
        }}

        function loadPaper(paper, liElement) {{
            // 핵심 수정 사항: srcdoc 속성에 HTML 문자열을 직접 주입
            frame.srcdoc = paper.content;
            
            if (activeItem) activeItem.classList.remove('active');
            liElement.classList.add('active');
            activeItem = liElement;
        }}

        function filterPapers() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const filtered = papers.filter(p => p.label.toLowerCase().includes(query));
            renderList(filtered);
        }}

        renderList(papers);
    </script>
</body>
</html>
            """
            
            with open(output_path, "w", encoding='utf-8') as f:
                f.write(single_html_content)
            
            print(f"Single-file visualization created at: {output_path}")
            
        except Exception as e:
            logging.error(f"Error creating visualization: {e}")
            logging.debug("Full error:", exc_info=True)
