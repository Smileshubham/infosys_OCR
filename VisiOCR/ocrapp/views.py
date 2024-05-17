import cv2
import numpy as np
import pytesseract
from datetime import datetime
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import re
# from django.template.loader import get_template
import pdfkit
from django.template.loader import render_to_string

from PIL import Image, ImageDraw, ImageFont
import io

def home(request):
    return render(request, 'ocr_app/home.html')

def preprocess_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    processed_image = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    return processed_image

def extract_info(image):
    processed_image = preprocess_image(image)
    text = pytesseract.image_to_string(processed_image)
    print("Extracted Text:")
    print(text)
    name, birth_date, unique_number = parse_text(text) 
    return name, birth_date, unique_number

def parse_text(text):
    name = None
    birth_date = None
    unique_number = None

    all_text_list = re.split(r'[\n]', text)
    text_list = list()
    
    numb = r'(\d+\s+\d+\s+\d+)|[A-Z]{5}[0-9]{4}[A-Z]{1}'
    unique = re.search(numb, text)
    if unique:
        unique_number = unique.group(0).strip()

    for i in all_text_list:
        if re.match(r'^(\s)+$', i) or i == '':
            continue
        else:
            text_list.append(i)
    print(text_list)

    if "MALE" in text or "male" in text or "FEMALE" in text or "female" in text:
        name = aadhar_name(text_list)
        print("aadhar name: ", name)
    else:
        name = pan_name(text)
        print("pan name:", name)

    dob_match_pan = re.search(r'(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
    if dob_match_pan:
        birth_date = dob_match_pan.group(0).strip()
    print("num", unique_number)
    return name, birth_date, unique_number

def aadhar_name(text_list):
    user_dob = str()
    user_name = str()
    aadhar_dob_pat = r'(YoB|YOB:|DOB:|DOB|AOB)'
    date_ele = str()
    index = None
    for idx, i in enumerate(text_list):
        if re.search(aadhar_dob_pat, i):
            index = re.search(aadhar_dob_pat, i).span()[1]
            date_ele = i
            dob_idx = idx
        else:
            continue

    if index is not None:
        date_str = ''
        for i in date_ele[index:]:
            if re.match(r'\d', i):
                date_str = date_str + i
            elif re.match(r'/', i):
                date_str = date_str + i
            else:
                continue

        user_dob = date_str
        user_name = text_list[dob_idx - 1]
        pattern = re.search(r'([A-Z][a-zA-Z\s]+)', user_name)
        if pattern:
            name = pattern.group(0).strip()
        else:
            name = None
        return name
    else:
        return None

def pan_name(text):
    pancard_name = None
    name_patterns = [
        r'(Name\s*\n[A-Z]+[\s]+[A-Z]+[\s]+[A-Z]+[\s])',
        r'(Name\s*\n[A-Z]+[\s]+[A-Z]+[\s])',
        r'(Name\s*\n[A-Z\s]+)'
    ]
    for pattern in name_patterns:
        name_match_pan = re.search(pattern, text)
        if name_match_pan:
            matched_name = name_match_pan.group(1).strip().replace('\n', ' ')
            pancard_name = re.sub(r'^Name\s+', '', matched_name)
            break
    return pancard_name

def process_image(image):
    name, birth_date, unique_number = extract_info(image)
    if birth_date is None:
        return name, None, None, None 
    else:
        age = calculate_age(birth_date)
    return name, birth_date, age, unique_number

def calculate_age(birth_date_str):
    try:
        birth_date_formats = ['%d-%m-%Y', '%d/%m/%Y', '%m-%d-%Y', '%m/%d/%Y']
        for fmt in birth_date_formats:
            try:
                birth_date = datetime.strptime(birth_date_str, fmt)
                break
            except ValueError:
                continue
        else:
            return None  # If no formats matched, return None

        age = (datetime.now() - birth_date).days // 365
        return age
    except (ValueError, TypeError):
        return None

@csrf_exempt 
def upload_image(request):
    if request.method == 'POST':
        if 'image' in request.FILES:
            uploaded_file = request.FILES['image']
            image = cv2.imdecode(np.frombuffer(uploaded_file.read(), np.uint8), -1)
            name, birth_date, age, unique_number = process_image(image)
            if birth_date is None or name is None:
                return render(request, 'ocr_app/home.html', {'error_message': "Image quality is too poor. Please try again or add the details manually."})
            return render(request, 'ocr_app/home.html', {'name': name, 'birth_date': birth_date, 'age': age, 'unique_number': unique_number})
        else:
            # user input
            name = request.POST.get('name')
            birth_date = request.POST.get('birth_date')
            age = calculate_age(birth_date)
            unique_number = request.POST.get('unique_number')
            phone = request.POST.get('phone')
            return render(request, 'ocr_app/home.html', {'name': name, 'birth_date': birth_date, 'unique_number': unique_number, 'age': age, 'phone': phone})

    return render(request, 'ocr_app/home.html')

def download_pdf(request):
    template_path = 'ocr_app/pdf_template1.html'

    context = {
        'name': request.POST.get('name'),
        'birth_date': request.POST.get('birth_date'),
        'age': request.POST.get('age'),
        'unique_number': request.POST.get('unique_number'),
        'phone': request.POST.get('phone')
    }

    html = render_to_string(template_path, context)
    path_to_wkhtmltopdf='/usr/local/bin/wkhtmltopdf'
    
    # Configure pdfkit to use wkhtmltopdf
    config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)

    # Generate PDF from HTML
    pdf = pdfkit.from_string(html, False, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="visiting_pass.pdf"'
    return response
# def  download_pdf(request):
#     name = request.POST.get('name')
#     birth_date = request.POST.get('birth_date')
#     age = request.POST.get('age')
#     unique_number = request.POST.get('unique_number')
#     phone = request.POST.get('phone')

#    # Create an image with higher resolution
#     width, height = 1200, 600
#     image = Image.new('RGB', (width, height), color=(255, 255, 255))
#     draw = ImageDraw.Draw(image)

#     font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # Adjust the font path to a valid TTF font on your system
#     try:
#         font = ImageFont.truetype(font_path, 40)
#     except IOError:
#         font = ImageFont.load_default()

#     # Draw the black bar on the left
#     draw.rectangle([(0, 0), (240, height)], fill="black")

#     # Draw the text on the left bar
#     draw.text((20, 100), f"{phone}", fill="white", font=font)
#     draw.text((20, 500), f"{age}", fill="white", font=font)

#     # Draw the main content
#     draw.text((260, 20), f"INFOSYS SPRINGBOARD", fill="black", font=font)
#     draw.text((260, 100), f"{name}", fill="black", font=font)
#     draw.text((260, 180), f"DOB: {birth_date}", fill="black", font=font)
#     draw.text((260, 260), f"Unique Number: {unique_number}", fill="black", font=font)

#     # Draw the right bar
#     draw.rectangle([(960, 0), (width, height)], fill="#f5ebe0")
#     draw.text((980, 300), f"Mobile Number: {phone}", fill="black", font=font)

#     buffer = io.BytesIO()
#     image.save(buffer, format="PNG")
#     buffer.seek(0)

#     response = HttpResponse(buffer, content_type="image/png")
#     response['Content-Disposition'] = 'attachment; filename="visiting_pass.png"'
#     return response