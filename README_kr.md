# **Scientific Paper Info Extractor & Graph Builder (Advanced)**

이 도구는 과학 논문 초록(Abstract)에서 구조화된 정보(배경, 목적, 방법론, 결과)를 추출하고, 의미론적(Semantic) 분석을 통해 \*\*지식 그래프(Knowledge Graph)의 Node/Edge List\*\*를 구축하며, 이를 html파일로 시각화하는 파이프라인입니다.

최신 업데이트를 통해 **Pydantic 기반의 엄격한 데이터 검증**, **유사 엔티티 자동 병합(Entity Resolution)**, 그리고 **멀티프로세싱 기반의 고속 시각화** 기능이 추가되었습니다.

---

## **✨ 주요 기능 (Key Features)**

1. **Structured Extraction (with Pydantic)**:  
   * LLM이 정의된 JSON 스키마를 100% 준수하도록 강제합니다.  
   * 데이터 누락이나 형식이 깨지는 문제를 원천 차단합니다.  
2. **Advanced Entity Resolution**:  
   * 단순 텍스트 매칭이 아닌, **임베딩(Embedding)** 유사도와 **LLM**을 활용하여 동의어를 하나로 통합합니다.  
   * *예: "CNN", "ConvNet", "Convolutional Neural Network" → "Convolutional Neural Network"로 정규화*  
3. **High-Performance Visualization**:  
   * 계산 비용이 높은 텍스트 정렬(Alignment) 작업에 \*\*병렬 처리(Multiprocessing)\*\*를 도입하여 속도를 획기적으로 개선했습니다.  
4. **Auto-Thresholding Graph**:  
   * 데이터 분포에 따라 그래프 연결 강도를 자동으로 조절하여 최적의 네트워크 구조를 생성합니다.

---

## **🚀 설치 (Setup)**

Python 3.8 이상이 필요합니다. 아래 명령어로 필수 패키지를 설치하세요.

Bash

pip install pandas numpy pyyaml tqdm langextract pydantic networkx ollama

   Bash  
   python3 src/main.py \--config config.yaml

---

## **📊 출력 결과 (Output)**

결과는 Output/generated/ 디렉토리에 저장됩니다.

* **CSV Data** (Graph Database용):  
  * papers.csv: 논문 노드 데이터.  
  * entities.csv: 정규화(Canonicalized)된 엔티티 노드 데이터.  
  * relations.csv: 논문-엔티티, 엔티티-엔티티 간의 관계 데이터.  
* **Interactive Dashboard**:  
  * graph\_visualization.html: **메인 대시보드 파일**. 브라우저에서 열어 모든 논문을 탐색할 수 있습니다.  
  * extraction\_results.jsonl: 추출 및 정렬된 원본 데이터.

---

## **🖼️ 시각화 예시 (Visualization Example)**

![Graph Visualization Example](graph_visualization_example.png)

---

## **🧠 시스템 로직 및 알고리즘**

### **1\. Extraction Logic (src/extractor.py)**

* **Schema Enforcement**: Pydantic 모델을 사용하여 LLM에게 엄격한 JSON 스키마를 주입합니다.  
* **Validation**: 추출된 데이터가 스키마와 일치하지 않을 경우(필드 누락, 타입 오류 등), 자동으로 필터링하거나 오류를 처리하여 데이터 무결성을 보장합니다.

### **2\. Graph Builder Logic (src/graph\_builder.py)**

이 모듈은 단순한 연결을 넘어 지식의 \*\*정제(Refinement)\*\*를 수행합니다.

* **Entity Resolution (개체명 정규화)**:  
  1. **Embedding**: 모든 추출된 엔티티(예: "SVM", "Support Vector Machine")의 벡터 임베딩을 계산합니다.  
  2. **Semantic Clustering**: 코사인 유사도(Cosine Similarity)를 기반으로 의미적으로 유사한 엔티티들을 군집화(NetworkX Connected Components)합니다.  
  3. **Canonicalization (LLM)**: 각 군집에 대해 LLM에게 "가장 표준적인 학술 용어(Canonical Name)"를 질의하여 대표 이름을 선정합니다.  
  4. **Merge**: 그래프 구축 시 원본 텍스트를 대표 이름으로 자동 치환하여 노드 중복을 제거합니다.  
* **Semantic Relation**:  
  * 엔티티 간의 유사도를 계산하고, similarity.mode: "auto" 설정 시 상위 N%의 강한 연결만 남겨 그래프가 복잡해지는(Hairball) 현상을 방지합니다.

### **3\. Visualizer Logic (src/visualizer.py)**

* **Parallel Alignment**:  
  * LLM이 추출한 텍스트가 원본 초록의 어느 위치에 있는지 찾는(Alignment) 작업은 CPU 연산이 많습니다.  
  * ProcessPoolExecutor를 사용하여 CPU 코어 수만큼 병렬로 작업을 처리, 대량의 논문 처리 속도를 비약적으로 높였습니다.  
* **Multi-Document Player**:  
  * langextract 라이브러리를 기반으로, 검색 및 필터링이 가능한 사이드바와 개별 논문 뷰어가 결합된 통합 HTML 대시보드를 생성합니다.

---

## **📂 파일 구조 (File Structure)**

```text
.
├── Input
│   └── rawdata.csv              # 논문 초록이 포함된 CSV 파일
├── Output
│   └── generated/               # 생성된 결과물 (HTML, CSV, JSONL)
├── src
│   ├── main.py                  # 메인 실행 파일
│   ├── extractor.py             # Pydantic 기반 구조화된 정보 추출
│   ├── graph_builder.py         # Entity Resolution 및 그래프 구축
│   ├── visualizer.py            # 멀티프로세싱 시각화 엔진
│   └── ollama_client.py         # Ollama API 클라이언트
├── config.yaml                  # 전체 설정 파일
└── README.md                    # 설명서
```

---

## System Architecture

graph TD
    %% 스타일 정의
    classDef input fill:#f9f,stroke:#333,stroke-width:2px,color:black;
    classDef module fill:#e1f5fe,stroke:#0277bd,stroke-width:2px,color:black;
    classDef logic fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,stroke-dasharray: 5 5,color:black;
    classDef storage fill:#e0f2f1,stroke:#00695c,stroke-width:2px,color:black;
    classDef output fill:#dcedc8,stroke:#558b2f,stroke-width:2px,color:black;

    %% 1. 입력 단계
    Input([📄 Raw Text<br/>논문 초록 Abstract]):::input
    
    %% 2. Extraction 단계
    subgraph S1 [Phase 1: Extraction]
        direction TB
        Extractor(extractor.py):::module
        LLM{LLM + Pydantic}:::logic
        DataStruct[구조화된 JSON<br/>Background, Purpose,<br/>Methodology, Results]:::storage
        
        Input --> Extractor
        Extractor --> LLM
        LLM -- Schema Parsing --> DataStruct
    end

    %% 3. Graph Builder 단계
    subgraph S2 [Phase 2: Graph Building]
        direction TB
        Builder(graph_builder.py):::module
        ER{Entity Resolver<br/>임베딩 유사도 분석}:::logic
        Files[CSV Files<br/>Nodes & Edges]:::storage
        
        DataStruct --> Builder
        Builder -- Node/Edge 생성 --> ER
        ER -- 동의어 통합 (Canonicalization) --> Files
    end

    %% 4. Visualizer 단계
    subgraph S3 [Phase 3: Visualization]
        direction TB
        Vis(visualizer.py):::module
        Aligner{Word Aligner<br/>원본-추출 텍스트 매핑}:::logic
        HTML[Interactive HTML<br/>Highlighting UI]:::output

        Files --> Vis
        Input -.-> Vis
        Vis --> Aligner
        Aligner --> HTML
    end

    %% 흐름 연결
    S1 ==> S2
    S2 ==> S3

## **License**

MIT License
