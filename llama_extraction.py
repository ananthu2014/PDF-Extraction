import os
import json
import argparse
from typing import List
from pydantic import BaseModel
from llama_extract import LlamaExtract
import asyncio
from PIL import Image
import pytesseract
import re
from PyPDF2 import PdfReader
import pandas as pd

'''Here, pytesseract is an Optical Character Recognition(OCR) library to scan the images and extract text data
   Llama extract is used to extract data from the PDFs directly, which is an AI-based tool'''

'''We have to manually create a schema for Llama extract to work for our specific cases as the default schemas were of different template from the given data. Use schema.update()
function to update the given scheme template.
Refer https://docs.cloud.llamaindex.ai/llamaextract/features/schemas for more informations'''

'''This function can also be used to extract text from PDFs'''

def extract_text_from_pdf(pdf_file_path):
    reader = PdfReader(pdf_file_path)
    text = ''
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def safe_extract(regex, text, group_num=1, default=None):
    match = re.search(regex, text)
    return match.group(group_num) if match else default

'''This is a function written manually using Regulr expressions to parse through the extracted data from images''' 
def extract_invoice_details(text):
    details = {}
    pattern_com = r'R E C I P I E N T(.*?)GSTIN'
    match_com = re.search(pattern_com, text, re.DOTALL)
    details['Company'] = match_com.group(1).strip() if match_com else ''
    details['Company_GSTIN'] = safe_extract(r'GSTIN\s*([A-Z0-9]+)', text)  
    pattern_add = r'GSTIN\s*([A-Z0-9]+)(.*?)Mobile'
    match_add = re.search(pattern_add, text, re.DOTALL)
    details["Company_Address"] = match_add.group(2).strip() if match_add else ''
    details['Company_Mobile'] = safe_extract(r'Mobile\s*\+?(\d{1,3}\s*\d+)', text)  
    details['Company_Email'] = safe_extract(r'Email\s*([\w\.-]+@[\w\.-]+)', text) 

    # Extract invoice number, date, and due date
    details['Invoice Number'] = safe_extract(r'Invoice #:\s*(INV-\d+)', text)
    details['Invoice Date'] = safe_extract(r'Invoice Date:\s*([\d]{2}\s[\w]{3}\s[\d]{4})', text)
    details['Due Date'] = safe_extract(r'Due Date:\s*([\d]{2}\s[\w]{3}\s[\d]{4})', text)

    # Extract customer details
    details['Customer_Name'] = safe_extract(r'Customer Details:\s*([\w\s]+)(?=\nPh|$)', text)
    details['Customer_Phone'] = safe_extract(r'Ph:\s*([\d]+)', text)

    # Extract shipping address
    details['Customer_Shipping/Billing Address'] = safe_extract(r'(?:Shipping Address|Billing Address):\s*([\w\s,]+)(?=\nPlace of Supply:|$)', text)  
    details['Place of Supply'] = safe_extract(r'Place of Supply:\s*(\d{2}-[\w\s]+)', text)

    # Extract items
    pattern_items = r'ValueTax AmountAmount(.*?)Taxable Amount'
    match_items = re.search(pattern_items, text, re.DOTALL)
    items_section = match_items.group(1) if match_items else ''
    
    # Extract individual items from the items section
    item_pattern = r'(\w+)\s+(\d+)\s+₹([\d.,]+)\s+(\d+)\s+₹([\d.,]+)'  # Example pattern for items
    items = []

    for item_match in re.finditer(item_pattern, items_section):
        items.append({
            'Item_Number': item_match.group(1).strip(),
            'Item_Name': item_match.group(2).strip(),
            'Rate_per_Item': float(item_match.group(3).replace(',', '')),
            'Quantity': int(item_match.group(4)),
            'Taxable_Value': float(item_match.group(5).replace(',', '')),
            'Tax_Amount': 0.0,  # Placeholder for tax amount
            'Total_Amount': float(item_match.group(5).replace(',', ''))
        })

    details["Items"] = items

    # Extract total amounts
    details['Taxable_Amount'] = safe_extract(r'Total\s*₹([\d.,]+)', text) 
    details['Total_Amount'] = safe_extract(r'Total\s*₹([\d.,]+)', text)
    details['Total_Discount'] = safe_extract(r'Total Discount\s+₹([\d.,]+)', text)

    # Bank details 
    details['Payment_Details'] = {
        'Bank': safe_extract(r'Bank:\s*+([a-zA-Z\s]+)\n', text),
        'Account_Number': safe_extract(r'Account #:\s*+(\d+)', text),
        'IFSC_Code': safe_extract(r'IFSC Code:\s*([A-Za-z0-9]+)', text),
    }
    
    details['Authorized_Signatory'] = safe_extract(r'Authorized Signatory:\s*([\w\s]+)', text)

    return details

'''Here, a Llama-extractor needs a template schema to extract data from the invoices. We can use a pre-defined template schema also, but to improve the accuracy, it's better to create
a manual schema.'''

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
    Invoice_Number: str
    Invoice_Date: str
    Due_Date: str
    Customer_Name: str
    Items: List[Item]
    Taxable_Amount: float
    Total_Amount: float
    Total_Discount: float
    Payment_Details: PaymentDetails
    Authorized_Signatory: str

async def save_extracted_invoice(extracted_invoice, save_directory, source_name=None):
    if not os.path.exists(save_directory):
        os.mkdir(save_directory)

    
    if source_name:
        file_name = f'extracted_invoice_from_image_{os.path.basename(source_name)}.json'
    else:
        file_name = f'extracted_invoice_{extracted_invoice["Invoice_Number"]}.json'

    json_file_path = os.path.join(save_directory, file_name)
    with open(json_file_path, "w") as json_file:
        json.dump(extracted_invoice, json_file, indent=4)

    print(f"Extracted invoice saved to {json_file_path}")

async def extract_invoices(pdf_directory: str, save_directory: str, use_llama: bool):
    fnames = os.listdir(pdf_directory)
    fnames = [fname for fname in fnames if fname.endswith(".pdf") or fname.endswith(('.jpg', '.jpeg', '.png'))]
    fpaths = [os.path.join(pdf_directory, fname) for fname in fnames]

    '''Here, we initialise the Llama-extractor'''
    extractor = LlamaExtract(verbose=True) if use_llama else None

    '''Here, we call and create a schema using the manually-created template if using Llama'''
    schema_response = await extractor.acreate_schema("Receipt Schema", data_schema=InvoiceSchema) if use_llama else None
    print(f"Created schema ID: {schema_response.id}" if use_llama else "Using PDF processing without Llama")

    '''data extraction'''
    pdf_fpaths = [f for f in fpaths if f.endswith('.pdf')]
    if use_llama:
        pdf_responses = await extractor.aextract(
            schema_response.id, pdf_fpaths, response_model=InvoiceSchema
        )
        data = pdf_responses[0]

        # Processing the responses of the PDFs
        for response in data:
            extracted_invoice = {
                "Company_Name": response.data["Company_Name"],
                "GSTIN": response.data["GSTIN"],
                "Invoice_Number": response.data["Invoice_Number"],
                "Invoice_Date": response.data["Invoice_Date"],
                "Due_Date": response.data["Due_Date"],
                "Customer_Name": response.data["Customer_Name"],
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

    else:
        print('Llama is not used')
        for image_path in pdf_fpaths:
            text = extract_text_from_pdf(image_path)
            extracted_invoice = extract_invoice_details(text)
            await save_extracted_invoice(extracted_invoice, save_directory, source_name=image_path)

async def main():
    parser = argparse.ArgumentParser(description="Invoice extraction tool")
    parser.add_argument("-pdf_dir", type=str, help="Directory of PDFs/images")
    parser.add_argument("-save_dir", type=str, help="Directory to save extracted invoices")
    parser.add_argument("--use_llama", action='store_true', help="Use Llama Extract for processing")
    args = parser.parse_args()

    pdf_directory = args.pdf_dir
    save_directory = args.save_dir
    use_llama = args.use_llama

    await extract_invoices(pdf_directory, save_directory, use_llama)

if __name__ == "__main__":
    asyncio.run(main())
