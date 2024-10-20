# Invoice Extraction Tool

This project provides a tool to extract invoice details from PDF and image files (JPEG, PNG) using Optical Character Recognition (OCR) and data extraction techniques.

## Features

- Extracts text from PDF and image files.
- Uses `pytesseract` for OCR to extract text from images.
- Utilizes `LlamaExtract` to extract structured data from PDFs.
- Regular expressions are used to parse the extracted text for relevant invoice details.
- Also, you can choose whether to run using Llama or not by specifying in the arguments. If not needed, it will use pyPDF2 to perform this action.

## Dependencies

To run this project, you'll need the following Python packages:

- `pytesseract`: For Optical Character Recognition (OCR).
- `PyPDF2`: For reading PDF files.
- `pydantic`: For data validation and settings management.
- `pandas`: For data manipulation and analysis.
- `llama-extract`: For structured data extraction from PDFs.

You can install the required packages using:

pip install -r requirements.txt

The result for image extraction can be found here: https://github.com/ananthu2014/PDF-Extraction/blob/main/Results/extracted_invoice_from_image_page_0.jpg.json  
All the results are given in the Results folder  
For further clarity, please check the project report.  
