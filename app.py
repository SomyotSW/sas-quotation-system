from flask import Flask, render_template, request, redirect, url_for
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv
from datetime import datetime
import os
import json
from io import StringIO
import smtplib
from email.message import EmailMessage

# Load .env
load_dotenv()

# Init Flask
app = Flask(__name__)
app.secret_key = os.getenv("Hihitler888")

# Init Firebase from ENV
firebase_key_str = os.getenv("FIREBASE_KEY_JSON")
firebase_key = json.load(StringIO(firebase_key_str))
cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred, {
    'storageBucket': f"{os.getenv('FIREBASE_PROJECT_ID')}.appspot.com"
})
db = firestore.client()
bucket = storage.bucket()

# ====== Upload file to Firebase ======
def upload_file_to_firebase(file, folder_name="uploads"):
    if file and hasattr(file, 'filename') and file.filename:
        blob = bucket.blob(f"{folder_name}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        blob.upload_from_file(file.stream, content_type=file.content_type)
        blob.make_public()
        return blob.public_url
    return ''

# ====== Send Email Notification ======
def send_notification_email(sale_name, customer_name, customer_company, pdf_url):
    msg = EmailMessage()
    msg['Subject'] = f"[SAS] ใบเสนอราคาสำเร็จ - ลูกค้า {customer_company}"
    msg['From'] = "somyotsw442@gmail.com"
    msg['To'] = "Somyot@synergy-as.com"
    msg['Cc'] = "traiwit@synergy-as.com, kongkiat@synergy-as.com"

    body = f"""
    📌 ใบเสนอราคาสำเร็จแล้ว

    ▪️ Sale: {sale_name}
    ▪️ ลูกค้า: {customer_name}
    ▪️ บริษัท: {customer_company}
    ▪️ Link: {pdf_url}

    กรุณาตรวจสอบและติดตามผลการขายต่อไปครับ
    """
    msg.set_content(body)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login('somyotsw442@gmail.com', 'dfwj earf bvuj jcrv')
        smtp.send_message(msg)

# ====== Home ======
@app.route('/')
def index():
    return render_template('index.html')

# ====== Request Form ======
@app.route('/request', methods=['GET', 'POST'])
def request_form():
    if request.method == 'POST':
        form = request.form
        files = request.files

        image_model_url = upload_file_to_firebase(files.get('image_model'), "model")
        image_motor_url = upload_file_to_firebase(files.get('image_motor'), "motor")
        image_ratio_url = upload_file_to_firebase(files.get('image_ratio'), "ratio")
        install_direction_url = upload_file_to_firebase(files.get('install_direction'), "install")

        data = {
            'sale_name': form.get('sale_name', ''),
            'customer_name': form.get('customer_name', ''),
            'phone': form.get('phone', ''),
            'customer_company': form.get('customer_company', ''),
            'purpose': form.get('purpose', ''),
            'model_old': form.get('model_old', ''),
            'motor_w': form.get('motor_w', ''),
            'motor_hp': form.get('motor_hp', ''),
            'motor_kw': form.get('motor_kw', ''),
            'ratio': form.get('ratio', ''),
            'shaft': form.get('shaft', ''),
            'timestamp': datetime.now().isoformat(),
            'status': 'waiting',
            'image_model_url': image_model_url,
            'image_motor_url': image_motor_url,
            'image_ratio_url': image_ratio_url,
            'install_direction_url': install_direction_url
        }

        db.collection('quotations').add(data)
        return redirect(url_for('index'))

    return render_template('request_form.html')

# ====== Dashboard ======
@app.route('/dashboard')
def dashboard():
    docs = db.collection('quotations').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    entries = [doc.to_dict() | {'id': doc.id} for doc in docs]
    return render_template('dashboard.html', entries=entries)

# ====== Upload Quotation PDF ======
@app.route('/upload_pdf/<doc_id>', methods=['POST'])
def upload_pdf(doc_id):
    pdf_file = request.files['pdf_file']
    if not pdf_file or not pdf_file.filename:
        return "No PDF selected", 400

    pdf_url = upload_file_to_firebase(pdf_file, folder_name="quotation_pdf")

    doc_ref = db.collection('quotations').document(doc_id)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        doc_ref.update({
            'status': 'sent',
            'quotation_pdf_url': pdf_url
        })

        send_notification_email(
            sale_name=data.get('sale_name'),
            customer_name=data.get('customer_name'),
            customer_company=data.get('customer_company'),
            pdf_url=pdf_url
        )

    return redirect(url_for('dashboard'))

# ====== Run Local ======
if __name__ == '__main__':
    app.run(debug=True)