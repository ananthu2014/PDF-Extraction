import os
import json
import argparse
from typing import List
from pydantic import BaseModel
import nest_asyncio
import asyncio
from llama_extract import LlamaExtract
from PIL import Image
import pytesseract
import re
from PyPDF2 import PdfReader
import fitz  # PyMuPDF

nest_asyncio.apply()

# Function to extract text from images using Tesseract
def extract_text_from_image(image_file_path):
    try:
        # Open the image file
        image = Image.open(image_file_path)
        # Use Tesseract to extract text
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        print(f"Error extracting text from image {image_file_path}: {e}")
        return ""

# Function to extract text from PDFs using PyPDF2
def extract_text_from_pdf(pdf_file_path):
    try:
        reader = PdfReader(pdf_file_path)
        text = ''
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Error extracting text from PDF {pdf_file_path}: {e}")
        return ""

# Utility function for safe extraction using regex
def safe_extract(regex, text, group_num=1, default=None):
    match = re.search(regex, text)
    return match.group(group_num) if match else default

# Function to extract images from PDFs
def extract_images_from_pdf(pdf_file_path):
    images = []
    try:
        doc = fitz.open(pdf_file_path)
        for page in doc:
            for img_index in range(len(page.get_images(full=True))):
                img = page.get_images(full=True)[img_index]
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                images.append(image_bytes)
        doc.close()
    except Exception as e:
        print(f"Error extracting images from PDF {pdf_file_path}: {e}")
    return images

# Function to extract invoice details using regex patterns
def extract_invoice_details(text):
    details = {}
    # Extracting Company Details
    pattern_com = r'R E C I P I E N T(.*?)GSTIN'
    match_com = re.search(pattern_com, text, re.DOTALL)
    result_com = match_com.group(1) if match_com else ""
    details['Company'] = result_com.replace('\n', " ").strip()
    details['Company_GSTIN'] = safe_extract(r'GSTIN\s*([A-Z0-9]+)', text)

    pattern_add = r'GSTIN\s*([A-Z0-9]+)(.*?)Mobile'
    match_add = re.search(pattern_add, text, re.DOTALL)
    result_add = match_add.group(2) if match_add else ""
    details["Company_Address"] = result_add.replace('\n', " ").strip()
    details['Company_Mobile'] = str(safe_extract(r'Mobile\s*\+?(\d{1,3}\s*\d+)', text))
    details['Company_Email'] = safe_extract(r'Email\s*([\w\.-]+@[\w\.-]+)', text)

    # Extract invoice number, date, and due date
    details['Invoice Number'] = safe_extract(r'Invoice #:\s*(INV-\d+)', text)
    details['Invoice Date'] = safe_extract(r'Invoice Date:\s*([\d]{2}\s[\w]{3}\s[\d]{4})', text)
    details['Due Date'] = safe_extract(r'Due Date:\s*([\d]{2}\s[\w]{3}\s[\d]{4})', text)

    # Extract customer details
    Customer_Phone = safe_extract(r'Ph:\s*([\d]+)', text)
    if Customer_Phone is not None:
        details['Customer_Name'] = safe_extract(r'Customer Details:\s*([\w\s]+)(?=\nPh|$)', text)
        details['Customer_Phone'] = str(safe_extract(r'Ph:\s*([\d]+)', text))
    else:
        details['Customer_Name'] = safe_extract(r'Customer Details:\s*([\w\s]+)\n', text)
        details['Customer_Phone'] = str(safe_extract(r'Ph:\s*([\d]+)', text))

    # Extract shipping address
    details['Customer_Shipping/Billing Address'] = safe_extract(r'(?:Shipping Address|Billing Address):\s*([\w\s,]+)(?=\nPlace of Supply:|$)', text)
    if details['Customer_Shipping/Billing Address'] is not None:
        details['Customer_Shipping/Billing Address'] = details['Customer_Shipping/Billing Address'].replace("\n", " ")
    details['Place of Supply'] = safe_extract(r'Place of Supply:\s*(\d{2}-[\w\s]+)', text).replace("\n", " ")

    # Extract items
    pattern = r'ValueTax AmountAmount(.*?)Taxable Amount'
    match = re.search(pattern, text, re.DOTALL)
    result = match.group(1) if match else None
    details["Item_List"] = result

    # Extract total amounts
    details['Total Amount'] = safe_extract(r'Total\s*₹([\d.,]+)', text)
    details['Total Discount'] = safe_extract(r'Total Discount\s+₹([\d.,]+)', text)

    # Bank details
    details['Bank_Details'] = safe_extract(r'Bank:\s*([a-zA-Z\s]+)\n', text)
    details['Account#'] = safe_extract(r'Account #:\s*(\d+)', text)
    details['IFSC_Code'] = safe_extract(r'IFSC Code:\s*([A-Za-z0-9]+)', text)
    details['Branch'] = safe_extract(r'Branch:\s*([A-Z\s-]+)\n', text)

    return details

# Pydantic models for invoice schema
class Item(BaseModel):
    Item_Number: str
    Item_Name: str
    Rate_per_Item: float
    Quantity: int
    Taxable_Value: float
    Tax_Amount: float
    Total_Amount: float

class PaymentDetails(BaseModel):
    Bank: str
    Account_Number: str
    IFSC_Code: str

class InvoiceSchema(BaseModel):
    Company_Name: str
    GSTIN: str
    Company_Address: str
    Invoice_Number: str
    Invoice_Date: str
    Due_Date: str
    Customer_Name: str
    Shipping_address: str
    Place_of_supply: str
    Items: List[Item]
    Taxable_Amount: float
    Total_Amount: float
    Total_Discount: float
    Payment_Details: PaymentDetails
    Authorized_Signatory: str

# Save extracted invoice to a JSON file
async def save_extracted_invoice(extracted_invoice, save_directory, source_name=None):
    os.makedirs(save_directory, exist_ok=True)  # Creates directories if they don't exist

    if source_name:
        file_name = f'extracted_invoice_from_image_{os.path.basename(source_name)}.json'
    else:
        file_name = f'extracted_invoice_{extracted_invoice["Invoice_Number"]}.json'

    json_file_path = os.path.join(save_directory, file_name)
    with open(json_file_path, "w") as json_file:
        json.dump(extracted_invoice, json_file, indent=4)

    print(f"Extracted invoice saved to {json_file_path}")

# Extract invoices from PDFs or images
async def extract_invoices(pdf_directory: str, save_directory: str, use_llama: bool):
    fnames = os.listdir(pdf_directory)
    fnames = [fname for fname in fnames if fname.endswith(('.pdf', '.jpg', '.jpeg', '.png'))]
    fpaths = [os.path.join(pdf_directory, fname) for fname in fnames]

    # Group files by type
    pdf_files = [fpath for fpath in fpaths if fpath.endswith('.pdf')]
    image_files = [fpath for fpath in fpaths if fpath.endswith(('.jpg', '.jpeg', '.png'))]

    extractor = LlamaExtract(verbose=True) if use_llama else None
    schema_response = None

    if use_llama:
        schema_response = await extractor.acreate_schema("Receipt Schema", data_schema=InvoiceSchema)
        print(f"Created schema ID: {schema_response.id}")

    # Combine PDF and image file paths if using Llama
    if use_llama:

        if pdf_files:
            # Process PDFs using Llama Extractor
            responses = await extractor.aextract(schema_response.id, pdf_files, response_model=InvoiceSchema)
            data  = responses[0]
            for response in data:
                extracted_invoice = {
                    "Company_Name": response.data["Company_Name"],
                    "GSTIN": response.data["GSTIN"],
                    "Company_Address": response.data["Company_Address"],
                    "Invoice_Number": response.data["Invoice_Number"],
                    "Invoice_Date": response.data["Invoice_Date"],
                    "Due_Date": response.data["Due_Date"],
                    "Customer_Name": response.data["Customer_Name"],
                    "Shipping_address": response.data['Shipping_address'],
                    "Place_of_supply": response.data['Place_of_supply'],
                    "Items": [
                        {
                            "Item_Number": item["Item_Number"],
                            "Item_Name": item["Item_Name"],
                            "Rate_per_Item": item["Rate_per_Item"],
                            "Quantity": item["Quantity"],
                            "Taxable_Value": item["Taxable_Value"],
                            "Tax_Amount": item["Tax_Amount"],
                            "Total_Amount": item["Total_Amount"]
                        }
                        for item in response.data["Items"]
                    ],
                    "Taxable_Amount": response.data["Taxable_Amount"],
                    "Total_Amount": response.data["Total_Amount"],
                    "Total_Discount": response.data["Total_Discount"],
                    "Payment_Details": {
                        "Bank": response.data["Payment_Details"]["Bank"],
                        "Account_Number": response.data["Payment_Details"]["Account_Number"],
                        "IFSC_Code": response.data["Payment_Details"]["IFSC_Code"],
                    },
                    "Authorized_Signatory": response.data["Authorized_Signatory"],
                }
                await save_extracted_invoice(extracted_invoice, save_directory)

            # Process any images in the PDFs
            for pdf_file in pdf_files:
                images = extract_images_from_pdf(pdf_file)
                for i, img_bytes in enumerate(images):
                    img_path = os.path.join(save_directory, f"extracted_image_{os.path.basename(pdf_file)}_{i}.png")
                    with open(img_path, "wb") as img_file:
                        img_file.write(img_bytes)
                    
                    # Use Tesseract to extract text from the saved image
                    text = extract_text_from_image(img_path)
                    extracted_invoice = extract_invoice_details(text)
                    await save_extracted_invoice(extracted_invoice, save_directory, source_name=img_path)

        if image_files:
            # Process each image separately
            for file_path in image_files:
                text = extract_text_from_image(file_path)
                extracted_invoice = extract_invoice_details(text)
                await save_extracted_invoice(extracted_invoice, save_directory, source_name=file_path)

    else:
        # Process each PDF separately
        for file_path in pdf_files:
            pdf_text = extract_text_from_pdf(file_path)
            extracted_invoice = extract_invoice_details(pdf_text)
            await save_extracted_invoice(extracted_invoice, save_directory, source_name=file_path)

        # Process each image separately
        for file_path in image_files:
            text = extract_text_from_image(file_path)
            extracted_invoice = extract_invoice_details(text)
            await save_extracted_invoice(extracted_invoice, save_directory, source_name=file_path)

# Main function to run the extraction process
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract invoices from PDFs and images.")
    parser.add_argument('--pdf_dir', type=str, required=True, help='Directory containing PDFs and images to extract invoices from')
    parser.add_argument('--save_dir', type=str, required=True, help='Directory to save extracted invoice JSON files')
    parser.add_argument('--use_llama', action='store_true', help='Use Llama Extractor for PDF processing')

    args = parser.parse_args()

    # Set your API key (ensure this is correct and secure)
    api_key = 'llx-ZFnxWNst0Cl24f4t0UN3xWoqXNwxrPFHBmvFudFalW1rSjQ8'
    os.environ["LLAMA_CLOUD_API_KEY"] = api_key

    asyncio.run(extract_invoices(args.pdf_dir, args.save_dir, args.use_llama))
