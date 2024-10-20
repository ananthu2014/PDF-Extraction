# Invoice Extraction Tool

This project provides a tool to extract invoice details from PDF and image files (JPEG, PNG) using Optical Character Recognition (OCR) and data extraction techniques.

## Features

- Extracts text from PDF and image files.
- Uses `pytesseract` for OCR to extract text from images.
- Utilizes `LlamaExtract` to extract structured data from PDFs.
- Regular expressions are used to parse the extracted text for relevant invoice details.

## Dependencies

To run this project, you'll need the following Python packages:

- `pytesseract`: For Optical Character Recognition (OCR).
- `PyPDF2`: For reading PDF files.
- `pydantic`: For data validation and settings management.
- `pandas`: For data manipulation and analysis.
- `llama-extract`: For structured data extraction from PDFs.

You can install the required packages using:

```bash
pip install pytesseract PyPDF2 pydantic pandas llama-extract
