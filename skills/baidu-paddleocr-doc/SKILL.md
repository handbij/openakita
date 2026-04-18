---
name: openakita/skills@baidu-paddleocr-doc
description: "PaddleOCR document parsing skill based on PaddleOCR-VL-1.5. Provides SOTA-level document understanding with ultra-high precision recognition and parsing. Use when user needs to parse, extract, or understand document content."
license: MIT
metadata:
  author: baidu
  version: "1.0.0"
requires:
  env: [BAIDU_API_KEY]
---

# Baidu PaddleOCR Document Parsing

Based on the SOTA document parsing model PaddleOCR-VL-1.5, giving the Agent "eyes" to perform ultra-high-precision document recognition and parsing.

## Configuration

export BAIDU_API_KEY="your_key"

## Features

- Document structure recognition
- Table extraction and reconstruction
- Formula recognition
- Mixed text-and-image analysis
- Multi-language document support

## Pre-built Scripts

### scripts/baidu_ocr_doc.py
Baidu document/table OCR recognition. Requires BAIDU_OCR_AK and BAIDU_OCR_SK to be set.

```bash
python3 scripts/baidu_ocr_doc.py doc /path/to/document.jpg
python3 scripts/baidu_ocr_doc.py table /path/to/table.png
```
