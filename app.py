from flask import Flask, render_template, request, redirect
from werkzeug.utils import secure_filename
import os
import firebase_admin
from firebase_admin import credentials, db, storage
from datetime import datetime
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from generate_pdf import generate_pdf

load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Firebase initialization
cred = credentials.Certificate("sas-transmission-firebase-adminsdk-fbsvc-964d6b7952.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://sas-transmission.asia-southeast1.firebasedatabase.app/',
    'storageBucket': 'sas-transmission.firebasestorage.app'
})
ref = db.reference("/quotations")
bucket = storage.bucket()

# Helper to upload files
def upload_file_to_firebase(file, folder_name="uploads"):
    if file and file.filename:
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
        blob = bucket.blob(f"{folder_name}/{filename}")
        blob.upload_from_file(file.stream, content_type=file.content_type)
        blob.make_public()
        return blob.public_url
    return ''

# Send email notification based on product type
def send_email_notification(data, attach_pdf_path=None):
    msg = EmailMessage()
    msg['Subject'] = '📨 ขอใบเสนอราคา SAS Transmission'
    product = data.get('product_type')

    # Determine recipients
    if product == 'Gear Motor':
        to_list = ['Somyot@synergy-as.com']
        cc_list = [
            'sas04@synergy-as.com', 'sas06@synergy-as.com',
            'kongkiat@synergy-as.com', 'traiwit@synergy-as.com'
        ]
    elif product == 'Conveyor & Automation':
        to_list = ['matinee@synergy-as.com', 'wiroj@synergy-as.com', 'sas04@synergy-as.com']
        cc_list = [
            'sas07@synergy-as.com', 'sas06@synergy-as.com',
            'kongkiat@synergy-as.com', 'traiwit@synergy-as.com'
        ]
    elif product == 'Structure':
        to_list = [
            'design_pp@hotmail.com', 'designsas2024@gmail.com',
            'tanin@synergy-as.com', 'Sukitkongprom@gmail.com',
            'SAS03@synergy-as.com', 'sas04@synergy-as.com'
        ]
        cc_list = [
            'design_pp@hotmail.com','designsas2024@gmail.com','tanin@synergy-as.com',
            'Sukitkongprom@gmail.com','SAS03@synergy-as.com','sas07@synergy-as.com',
            'sas06@synergy-as.com','kongkiat@synergy-as.com','traiwit@synergy-as.com',
            'sassynergy2024@outlook.com'
        ]
    else:
        to_list = [EMAIL_USER]
        cc_list = []

    msg['To'] = ', '.join(to_list)
    if cc_list:
        msg['Cc'] = ', '.join(cc_list)

    # Compose body
    content = f"""
📌 Sale: {data.get('sale_name','-')}
📧 Email: {data.get('sale_email','-')}
👤 ชื่อลูกค้า: {data.get('customer_name','-')}
📞 เบอร์โทรลูกค้า: {data.get('phone','-')}
🏢 บริษัทลูกค้า: {data.get('company','-')}
📦 สินค้า: {product}
🎯 วัตถุประสงค์: {data.get('purpose','-')}
🚀 ความเร่งด่วน: {data.get('quotation_speed','-')}
📅 เวลาที่ส่ง: {data.get('timestamp','-')}
"""
    msg.set_content(content)

    # Attach PDF if exists
    if attach_pdf_path:
        with open(attach_pdf_path, 'rb') as f:
            msg.add_attachment(
                f.read(), maintype='application', subtype='pdf',
                filename=os.path.basename(attach_pdf_path)
            )

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
    except Exception as e:
        print("❌ Error sending email:", e)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/form')
def form():
    return render_template('request_form.html')

@app.route('/dashboard')
def dashboard():
    quotations = ref.get() or {}
    sorted_data = sorted(quotations.items(), key=lambda x: x[1]['timestamp'], reverse=True)
    return render_template('dashboard.html', quotations=sorted_data)

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = {
            'sale_name': request.form.get('sale_name'),
            'sale_email': request.form.get('sale_email'),
            'customer_name': request.form.get('customer_name'),
            'phone': request.form.get('customer_phone'),
            'company': request.form.get('customer_company'),
            'product_type': request.form.get('product_type'),
            'purpose': request.form.get('purpose'),
            'quotation_speed': request.form.get('quotation_speed'),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'รอใบเสนอราคา'
        }

        product = data['product_type']

        # If 'วางแทนของเดิม', require specific images
        if data.get('purpose') == 'วางแทนของเดิม':
            file_fields = {
                'old_model_image':'old_model_image_url',
                'motor_image':'motor_image_url',
                'ratio_image':'ratio_image_url',
                'install_image':'install_image_url'
            }
            for fld, key in file_fields.items():
                f = request.files.get(fld)
                if not f or not f.filename:
                    return f"❌ ต้องแนบไฟล์สำหรับ '{fld}'", 400
                data[key] = upload_file_to_firebase(f, 'uploads')

        attach_pdf = None
        # Gear Motor: generate PDF
        if product == 'Gear Motor':
            pdf_path = generate_pdf(data)
            blob = bucket.blob(f"pdf/{os.path.basename(pdf_path)}")
            blob.upload_from_filename(pdf_path)
            blob.make_public()
            data['pdf_url'] = blob.public_url
            attach_pdf = pdf_path
        else:
            # Conveyor & Automation or Structure: handle extra_file
            extra = request.files.get('extra_file')
            if not extra or not extra.filename:
                return "❌ ต้องแนบไฟล์ Excel หรือ PDF", 400
            ext = os.path.splitext(extra.filename)[1].lower()
            if ext not in ['.pdf','.xls','.xlsx']:
                return "❌ ไฟล์ต้องเป็น .pdf, .xls หรือ .xlsx", 400
            data['attachment_url'] = upload_file_to_firebase(extra, 'attachments')

        ref.push(data)
        send_email_notification(data, attach_pdf_path=attach_pdf)
        return redirect('/dashboard')
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/update_status/<quote_id>', methods=['POST'])
def update_status(quote_id):
    # ... (unchanged) ...
    return redirect('/dashboard')

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(debug=True)
