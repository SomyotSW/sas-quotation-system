from flask import Flask, render_template, request, redirect, url_for
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv
from datetime import datetime
import os
import smtplib
from email.message import EmailMessage

# Load .env
load_dotenv()

# Init Flask
app = Flask(__name__)
app.secret_key = os.getenv("Hihitler888")

# Init Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': f"{os.getenv('FIREBASE_PROJECT_ID')}.appspot.com"
})
db = firestore.client()
bucket = storage.bucket()

# ====== Function: Upload file to Firebase Storage ======
def upload_file_to_firebase(file, folder_name="uploads"):
    if file and file.filename != '':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        blob = bucket.blob(f"{folder_name}/{timestamp}_{file.filename}")
        blob.upload_from_file(file)
        blob.make_public()
        return blob.public_url
    return ''

# ====== Function: Send notification email ======
def send_notification_email(sale_name, customer_name, customer_company, pdf_url):
    msg = EmailMessage()
    msg['Subject'] = f"[SAS] ใบเสนอราคาสำเร็จ - ลูกค้า {customer_company}"
    msg['From'] = "somyotsw442@gmail.com"  # ← เปลี่ยนเป็นอีเมลของคุณ
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
        smtp.login('somyotsw442@gmail.com', 'dfwj earf bvuj jcrv')  # ← ใส่รหัส App Password
        smtp.send_message(msg)

# ====== Route: Home ======
@app.route('/')
def index():
    return render_template('index.html')

# ====== Route: Request Form ======
@app.route('/request', methods=['GET', 'POST'])
def request_form():
    if request.method == 'POST':
        form = request.form
        files = request.files

        # Upload images to Firebase
        image_model_url = upload_file_to_firebase(files.get('image_model'), "model")
        image_motor_url = upload_file_to_firebase(files.get('image_motor'), "motor")
        image_ratio_url = upload_file_to_firebase(files.get('image_ratio'), "ratio")
        install_direction_url = upload_file_to_firebase(files.get('install_direction'), "install")

        # Prepare Firestore data
        data = {
            'sale_name': form.get('sale_name'),
            'customer_name': form.get('customer_name'),
            'phone': form.get('phone'),
            'customer_company': form.get('customer_company'),
            'purpose': form.get('purpose'),
            'model_old': form.get('model_old'),
            'motor_w': form.get('motor_w'),
            'motor_hp': form.get('motor_hp'),
            'motor_kw': form.get('motor_kw'),
            'ratio': form.get('ratio'),
            'shaft': form.get('shaft'),
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

# ====== Route: Dashboard ======
@app.route('/dashboard')
def dashboard():
    docs = db.collection('quotations').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    entries = [doc.to_dict() | {'id': doc.id} for doc in docs]
    return render_template('dashboard.html', entries=entries)

# ====== Route: Upload Quotation PDF ======
@app.route('/upload_pdf/<doc_id>', methods=['POST'])
def upload_pdf(doc_id):
    pdf_file = request.files['pdf_file']
    if not pdf_file or pdf_file.filename == '':
        return "No PDF selected", 400

    # Upload to Firebase
    pdf_url = upload_file_to_firebase(pdf_file, folder_name="quotation_pdf")

    # Update Firestore
    doc_ref = db.collection('quotations').document(doc_id)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        doc_ref.update({
            'status': 'sent',
            'quotation_pdf_url': pdf_url
        })

        # Send Email Notification
        send_notification_email(
            sale_name=data.get('sale_name'),
            customer_name=data.get('customer_name'),
            customer_company=data.get('customer_company'),
            pdf_url=pdf_url
        )

    return redirect(url_for('dashboard'))

# ====== Run App ======
if __name__ == '__main__':
    app.run(debug=True)
