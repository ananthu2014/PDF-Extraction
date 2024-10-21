# Invoice Extraction Tool

This project provides a tool to extract invoice details from PDF and image files (JPEG, PNG) using Optical Character Recognition (OCR) and data extraction techniques.

## Features

- Extracts text from PDF and image files.
- Uses `pytesseract` for OCR to extract text from images.
- Utilizes `LlamaExtract` to extract data from PDFs.
- Utilizes 'PyPDF' coupled with Regular-Expression parser to extract data from PDfs faster, but Llama-Extract is the most accurate soltuion.  
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

The result for image extraction can be found too, where the PDFs are converted to images for the purpose of writing the code and testing accordingly.  
All the results are given in the three Results folder.    
For further clarity, please check the project report.  
pdf_ext.ipynb is the work-space to show the progress.  
model.ipynb is the main file.  
sample.py is the file which also uses PyMuPDF Library to extract images inside the PDFs to parse that information as well, but the code is not tested and debugged properly.  
