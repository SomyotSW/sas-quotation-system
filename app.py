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

# Send initial quotation request email based on product type
def send_email_notification(data, attach_pdf_path=None):
    msg = EmailMessage()
    msg['Subject'] = '📨 ขอใบเสนอราคา SAS Transmission'
    product = data.get('product_type')
    # Determine recipients by product
    if product == 'Gear Motor':
        to_list = ['Somyot@synergy-as.com']
        cc_list = [
            'sas04@synergy-as.com',
            'sas06@synergy-as.com',
            'kongkiat@synergy-as.com',
            'traiwit@synergy-as.com'
        ]
    elif product == 'Conveyor & Automation':
        to_list = ['matinee@synergy-as.com', 'wiroj@synergy-as.com']
        cc_list = [
            'sas07@synergy-as.com',
            'sas06@synergy-as.com',
            'kongkiat@synergy-as.com',
            'traiwit@synergy-as.com'
        ]
    elif product == 'Structure':
        to_list = [
            'design_pp@hotmail.com',
            'designsas2024@gmail.com',
            'tanin@synergy-as.com',
            'Sukitkongprom@gmail.com',
            'SAS03@synergy-as.com'
        ]
        cc_list = [
            'design_pp@hotmail.com',
            'designsas2024@gmail.com',
            'tanin@synergy-as.com',
            'Sukitkongprom@gmail.com',
            'SAS03@synergy-as.com',
            'sas07@synergy-as.com',
            'sas06@synergy-as.com',
            'kongkiat@synergy-as.com',
            'traiwit@synergy-as.com',
            'sassynergy2024@outlook.com'
        ]
    else:
        to_list = [EMAIL_USER]
        cc_list = []

    msg['To'] = ', '.join(to_list)
    if cc_list:
        msg['Cc'] = ', '.join(cc_list)

    # Email body
    content = f"""
📌 ชื่อเซลล์: {data.get('sale_name', '-')}
📧 อีเมลเซลล์: {data.get('sale_email', '-')}
👤 ชื่อลูกค้า: {data.get('customer_name', '-')}
📞 เบอร์โทรลูกค้า: {data.get('phone', '-')}
🏢 บริษัทลูกค้า: {data.get('company', '-')}
📦 สินค้า: {product}
🎯 วัตถุประสงค์: {data.get('purpose', '-')}
🚀 ความเร่งด่วน: {data.get('quotation_speed', '-')}
📅 เวลาที่ส่ง: {data.get('timestamp', '-')}

🔗 ลิงก์ไฟล์ PDF: {data.get('pdf_url', '-')}
"""
    msg.set_content(content)

    # Attach PDF
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
    try:
        quotations = ref.get() or {}
        sorted_data = sorted(quotations.items(), key=lambda x: x[1]['timestamp'], reverse=True)
        return render_template('dashboard.html', quotations=sorted_data)
    except Exception as e:
        return f"Error loading dashboard: {e}", 500

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = {
            "sale_name": request.form.get("sale_name"),
            "sale_email": request.form.get("sale_email"),
            "customer_name": request.form.get("customer_name"),
            "phone": request.form.get("customer_phone"),
            "company": request.form.get("customer_company"),
            "product_type": request.form.get("product_type"),
            "purpose": request.form.get("purpose"),
            "motor_model": request.form.get("motor_model"),
            "motor_unit": request.form.get("motor_unit"),
            "ratio": request.form.get("gear_ratio"),
            "controller": request.form.get("controller"),
            "other_info": request.form.get("other_info"),
            "quotation_speed": request.form.get("quotation_speed"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "รอใบเสนอราคา"
        }

        # Handle file uploads for "วางแทนของเดิม"
        file_fields = {
            'old_model_image': 'old_model_image_url',
            'motor_image': 'motor_image_url',
            'ratio_image': 'ratio_image_url',
            'install_image': 'install_image_url'
        }
        if data['purpose'] == "วางแทนของเดิม":
            for field, key in file_fields.items():
                file = request.files.get(field)
                if not file or not file.filename:
                    return f"❌ ต้องแนบไฟล์สำหรับ '{field}'", 400
                data[key] = upload_file_to_firebase(file, "uploads")

        # Generate and upload PDF
        pdf_path = generate_pdf(data)
        pdf_filename = os.path.basename(pdf_path)
        blob = bucket.blob(f"pdf/{pdf_filename}")
        blob.upload_from_filename(pdf_path)
        blob.make_public()
        data["pdf_url"] = blob.public_url

        ref.push(data)
        send_email_notification(data, attach_pdf_path=pdf_path)
        return redirect('/dashboard')
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/update_status/<quote_id>', methods=['POST'])
def update_status(quote_id):
    file = request.files.get("quotation_file")
    uploader_email = request.form.get("uploader_email", "").strip()

    # Validate uploader email
    allowed_emails = {
        'Somyot@synergy-as.com', 'sas06@synergy-as.com', 'sas04@synergy-as.com',
        'matinee@synergy-as.com', 'wiroj@synergy-as.com',
        'design_pp@hotmail.com','designsas2024@gmail.com','tanin@synergy-as.com',
        'Sukitkongprom@gmail.com','SAS03@synergy-as.com','sassynergy2024@outlook.com'
    }
    if uploader_email not in allowed_emails:
        return "❌ ไม่อนุญาตให้อัปโหลดจากอีเมลนี้", 403

    # Validate file type
    if not file or not file.filename:
        return "❌ ไม่พบไฟล์", 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.xls', '.xlsx']:
        return "❌ อัปโหลดได้เฉพาะ .pdf, .xls, .xlsx เท่านั้น", 400

    try:
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
        blob = bucket.blob(f"quotations/{filename}")
        blob.upload_from_file(file.stream, content_type=file.content_type)
        blob.make_public()
        file_url = blob.public_url

        # Update database
        ref.child(quote_id).update({
            "status": "ส่งแล้ว",
            "quotation_file_url": file_url,
            "uploader_email": uploader_email
        })

        # Send reply email to original sale
        data = ref.child(quote_id).get()
        sale_email = data.get("sale_email")
        product = data.get("product_type")
        if sale_email:
            msg = EmailMessage()
            msg['Subject'] = '📩 ใบเสนอราคาจาก SAS Transmission'
            msg['From'] = EMAIL_USER
            msg['To'] = sale_email
            # Determine CC by product
            if product == 'Gear Motor':
                cc = [
                    'sas04@synergy-as.com','sas06@synergy-as.com',
                    'kongkiat@synergy-as.com','traiwit@synergy-as.com'
                ]
            elif product == 'Conveyor & Automation':
                cc = [
                    'sas07@synergy-as.com','sas06@synergy-as.com',
                    'kongkiat@synergy-as.com','traiwit@synergy-as.com'
                ]
            elif product == 'Structure':
                cc = [
                    'design_pp@hotmail.com','designsas2024@gmail.com','tanin@synergy-as.com',
                    'Sukitkongprom@gmail.com','SAS03@synergy-as.com',
                    'sas07@synergy-as.com','sas06@synergy-as.com',
                    'kongkiat@synergy-as.com','traiwit@synergy-as.com',
                    'sassynergy2024@outlook.com'
                ]
            else:
                cc = []
            if cc:
                msg['Cc'] = ', '.join(cc)

            msg.set_content(f"เรียนคุณ {data.get('sale_name','')},\n\nระบบได้แนบใบเสนอราคาที่คุณร้องขอไว้เรียบร้อยแล้ว\n\n🧾 ลิงก์ใบเสนอราคา: {file_url}\n\nขอบคุณที่ใช้บริการ SAS Transmission")

            with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
                smtp.starttls()
                smtp.login(EMAIL_USER, EMAIL_PASS)
                smtp.send_message(msg)

        return redirect('/dashboard')
    except Exception as e:
        return f"Error updating status: {e}", 500

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(debug=True)