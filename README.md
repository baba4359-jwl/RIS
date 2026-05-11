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

---

## Windows 설치 가이드

### 1단계 — 프로젝트 다운로드

아래 링크에서 ZIP 파일로 다운로드합니다.

> **https://github.com/baba4359-jwl/RIS** 접속 →
> 초록색 **`<> Code`** 버튼 클릭 → **`Download ZIP`** 선택

다운로드된 **`RIS-main.zip`** 을 원하는 위치에 압축 해제합니다.  
(예: `C:\RIS-main`)

> 압축 해제 후 폴더 안에 `start.bat`, `app_main.py` 등의 파일이 보이면 정상입니다.

### 2단계 — Python 3.11 설치

아래 링크에서 Python **3.11 64-bit** 설치 파일을 내려받아 실행합니다.

> **https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe**
>
> 파일명: **`python-3.11.9-amd64.exe`** (`amd64` = 64-bit, 이 파일을 받아야 합니다)

설치 화면 하단의 **"Add Python to PATH"** 에 반드시 체크한 뒤 **Install Now** 를 클릭합니다.

> ⚠️ Python 3.12 이상은 지원하지 않습니다. 반드시 **3.11** 을 설치해 주세요.

### 3단계 — 패키지 설치

압축 해제된 폴더 안에서 아래 명령어를 순서대로 실행합니다 **(최초 1회, 약 5~10분 소요)**.

cmd(명령 프롬프트)를 열고 압축 해제 폴더로 이동합니다.

```cmd
cd C:\RIS-main
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install --prefer-binary -r requirements.txt
```

> 설치 중 오류가 발생하면 Python 버전이 3.11.x인지, PATH가 올바르게 설정됐는지 확인합니다.

### 4단계 — 앱 실행

탐색기에서 압축 해제 폴더를 열고 **`start.bat`을 더블클릭**합니다.  
브라우저가 자동으로 열리고 앱이 실행됩니다.

> **두 번째 실행부터는** `start.bat` 더블클릭만 하면 바로 시작됩니다.

---

## Features

- pdfplumber + PyMuPDF 기반 PDF 파싱
- Sentence-aware 청킹 (512 tokens / 64 overlap)
- ChromaDB 벡터 스토어
- BM25 + Semantic 하이브리드 검색 (RRF)
- Voyage AI `rerank-2-lite` 재랭킹
- Groq 클라우드 LLM 기반 인용 강제 답변

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API 키 (console.groq.com 무료 발급) |
| `VOYAGE_API_KEY` | Yes | Voyage AI 키 (dash.voyageai.com 무료 발급) |
| `GROQ_MODEL` | No | 기본값: `llama-3.1-8b-instant` |
| `TOP_K_RETRIEVAL` | No | 검색 청크 수 (기본값: 10) |
| `TOP_K_RERANK` | No | 재랭킹 후 LLM 전달 청크 수 (기본값: 5) |
