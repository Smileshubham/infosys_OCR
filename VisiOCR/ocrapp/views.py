import cv2
import numpy as np
import pytesseract
from datetime import datetime
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import re
from django.template.loader import get_template
from xhtml2pdf import pisa

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
    name, birth_date = parse_text(text) 
    return name, birth_date

def parse_text(text):
    name = None
    birth_date = None

    all_text_list = re.split(r'[\n]', text)
    text_list = list()
    
    for i in all_text_list:
        if re.match(r'^(\s)+$', i) or i=='':
            continue
        else:
            text_list.append(i)
    print(text_list)

    if "MALE" in text or "male" in text or "FEMALE" in text or "female" in text :
        name=aadhar_name(text_list)
        print("aadhar name: ", name)
    else:
        name=pan_name(text)
        print("pan name:", name)

    dob_match_pan = re.search(r'(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
    if dob_match_pan:
        birth_date = dob_match_pan.group(0).strip() 
    return name, birth_date

def aadhar_name(text_list):
    user_dob = str()
    user_name = str()
    aadhar_dob_pat = r'(YoB|YOB:|DOB:|DOB|AOB)'
    date_ele = str()
    index = None  # Initialize index variable
    for idx, i in enumerate(text_list):
        if re.search(aadhar_dob_pat, i):
            index = re.search(aadhar_dob_pat, i).span()[1]
            date_ele = i
            dob_idx = idx
        else:
            continue

    if index is not None:  # Check if index is assigned a value
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
    pancard_name=None
    name_patterns = [
        r'(Name\s*\n[A-Z]+[\s]+[A-Z]+[\s]+[A-Z]+[\s])',  
        r'(Name\s*\n[A-Z]+[\s]+[A-Z]+[\s])', 
        r'(Name\s*\n[A-Z\s]+)'  
    ]
    for pattern in name_patterns:
            name_match_pan = re.search(pattern,text)
            if name_match_pan:
                matched_name = name_match_pan.group(1).strip().replace('\n', ' ') 
                pancard_name = re.sub(r'^Name\s+', '', matched_name)
                break
    return pancard_name

def process_image(image):
    name, birth_date = extract_info(image)
    if birth_date is None:
        return name, None, None 
    else:
        age=calculate_age(birth_date)
    return name, birth_date, age

def calculate_age(birth_date):
    try:
        birth_date_formats = ['%d-%m-%Y', '%d/%m/%Y', '%m-%d-%Y', '%m/%d/%Y']
        for fmt in birth_date_formats:
            try:
                birth_date = datetime.strptime(birth_date, "%d/%m/%Y")
                print(birth_date)
                break  
            except ValueError:
                continue
        age = (datetime.now() - birth_date).days // 365
    except (ValueError, TypeError):
        birth_date = None
        age = None
    return age

@csrf_exempt 
def upload_image(request):
    if request.method == 'POST':
        if 'image' in request.FILES:
            uploaded_file = request.FILES['image']
            image = cv2.imdecode(np.frombuffer(uploaded_file.read(), np.uint8), -1)
            name, birth_date, age = process_image(image)
            if birth_date is None or name is None:
                return render(request, 'ocr_app/home.html', {'error_message': "Image quality is too poor. Please try again or add the details manually."})
            return render(request, 'ocr_app/home.html', {'name': name, 'birth_date': birth_date, 'age': age})
        else:
            name = request.POST.get('name')
            birth_date = request.POST.get('birth_date')
            age = calculate_age(birth_date)
            return render(request, 'ocr_app/home.html', {'name': name, 'birth_date': birth_date, 'age': age})

    return render(request, 'ocr_app/home.html')

def download_pdf(request):
    template_path = 'ocr_app/pdf_template.html'
    context = {
        'name': request.POST.get('name'),
        'birth_date': request.POST.get('birth_date'),
        'age': request.POST.get('age'),
    }
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="visiting_pass.pdf"'
    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response