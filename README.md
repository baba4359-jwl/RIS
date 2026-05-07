---
title: PDF Research Intelligence
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.35.0
app_file: app_main.py
pinned: false
---

# 📄 PDF Research Intelligence (RIS)

PDF 문헌을 업로드하면 인용과 함께 답변하는 RAG 시스템.
**Groq 무료 API** 기반으로 빠른 클라우드 추론을 제공합니다.

## Features

- pdfplumber + PyMuPDF 기반 PDF 파싱
- Sentence-aware 청킹 (512 tokens / 64 overlap)
- ChromaDB 벡터 스토어
- BM25 + Semantic 하이브리드 검색 (RRF)
- Cross-encoder 재랭킹
- Groq 클라우드 LLM 기반 인용 강제 답변

## Setup (로컬 실행)

```bash
git clone https://github.com/baba4359-jwl/RIS
cd RIS
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

cp .env.example .env
# .env 에 GROQ_API_KEY 입력 (https://console.groq.com 에서 무료 발급)

streamlit run app_main.py
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API 키 (console.groq.com 무료 발급) |
| `GROQ_MODEL` | No | 기본값: `llama-3.1-8b-instant` |
| `TOP_K_RETRIEVAL` | No | 검색 청크 수 (기본값: 10) |
| `TOP_K_RERANK` | No | 재랭킹 후 LLM 전달 청크 수 (기본값: 5) |
