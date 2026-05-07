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

## Windows 설치 가이드 (아무것도 설치되지 않은 환경)

### 1단계 — Git 설치

Git이 없으면 아래 링크에서 설치합니다.

> https://git-scm.com/download/win
>
> 설치 시 옵션은 모두 기본값으로 진행해도 됩니다.

설치 후 바탕화면 또는 원하는 폴더에서 **우클릭 → "Open Git Bash here"** 를 선택합니다.

### 2단계 — 프로젝트 다운로드

Git Bash (또는 cmd / PowerShell) 에서 아래 명령어를 실행합니다.

```bash
git clone https://github.com/baba4359-jwl/RIS
cd RIS
```

### 3단계 — start.bat 실행

탐색기에서 `RIS` 폴더를 열고 **`start.bat`을 더블클릭**합니다.

> **Python이 없어도 괜찮습니다.**
> start.bat이 Python 3.12를 자동으로 설치합니다.
> (winget → 직접 다운로드 순서로 시도, 관리자 권한 불필요)

### 4단계 — API 키 입력 (최초 1회)

처음 실행 시 아래 두 가지 무료 API 키를 입력하라는 메시지가 나옵니다.

| 서비스 | 용도 | 발급 주소 |
|---|---|---|
| Groq | 답변 생성 LLM | https://console.groq.com |
| Voyage AI | 검색 재랭킹 | https://dash.voyageai.com |

두 서비스 모두 회원가입 후 무료로 발급 가능합니다.

### 5단계 — 완료

키 입력이 끝나면 패키지 설치가 시작됩니다 **(최초 1회, 약 5~10분 소요)**.
설치가 완료되면 브라우저가 자동으로 열리고 앱이 실행됩니다.

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
