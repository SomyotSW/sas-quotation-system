from flask import Flask, render_template, request, redirect
from werkzeug.utils import secure_filename
import os
import firebase_admin
from firebase_admin import credentials, db, storage
import datetime
import smtplib
from email.message import EmailMessage
from generate_pdf import generate_pdf  # <== ฟังก์ชันสร้าง PDF

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Firebase setup
cred = credentials.Certificate("sas-transmission-firebase-adminsdk-fbsvc-964d6b7952.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://sas-transmission.asia-southeast1.firebasedatabase.app/',
    'storageBucket': 'sas-transmission.firebasestorage.app'
})

ref = db.reference("/quotations")
bucket = storage.bucket()

# ====== Upload file to Firebase Storage ======
def upload_file_to_firebase(file, folder_name="uploads"):
    if file and file.filename:
        filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
        blob = bucket.blob(f"{folder_name}/{filename}")
        blob.upload_from_file(file.stream, content_type=file.content_type)
        blob.make_public()
        return blob.public_url
    return ''

# ====== Email Notification with PDF ======
def send_email_notification(data, attach_pdf_path=None):
    msg = EmailMessage()
    msg['Subject'] = '📨 ขอใบเสนอราคา SAS Transmission'
    msg['From'] = "noreply@motorsas.com"
    msg['To'] = "Somyot@synergy-as.com, sas06@synergy-as.com, sas04@synergy-as.com"
    msg['Cc'] = ""

    content = f"""
    📌 Sale: {data['sale_name']}
    📧 อีเมล Sale: {data['sale_email']}
    👤 ลูกค้า: {data['customer_name']}
    📞 เบอร์: {data['phone']}
    🏢 บริษัท: {data['company']}
    🎯 วัตถุประสงค์: {data['purpose']}
    📅 เวลา: {data['timestamp']}
    """
    msg.set_content(content)

    if attach_pdf_path:
        with open(attach_pdf_path, 'rb') as f:
            msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=os.path.basename(attach_pdf_path))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login("Somyotsw442@gmail.com", "dfwj earf bvuj jcrv")  # แนะนำให้ใช้ .env
            smtp.send_message(msg)
    except Exception as e:
        print("Error sending email:", e)

# ====== Routes ======

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/form')
def form():
    return render_template('request_form.html')

@app.route('/dashboard')
def dashboard():
    try:
        quotations = ref.get()
        sorted_data = sorted(quotations.items(), key=lambda x: x[1]['timestamp'], reverse=True) if quotations else []
        return render_template('dashboard.html', quotations=sorted_data)
    except Exception as e:
        return f"Error loading dashboard: {str(e)}"

@app.route('/submit', methods=['POST'])
def submit():
    data = {
        "sale_name": request.form.get("sale_name"),
        "sale_email": request.form.get("sale_email"),
        "customer_name": request.form.get("customer_name"),
        "phone": request.form.get("phone"),
        "company": request.form.get("company"),
        "purpose": request.form.get("purpose"),
        "old_model": request.form.get("old_model"),
        "motor_w": request.form.get("motor_w"),
        "motor_hp": request.form.get("motor_hp"),
        "motor_kw": request.form.get("motor_kw"),
        "ratio": request.form.get("ratio"),
        "shaft_size": request.form.get("shaft_size"),
        "no_shaft_info": request.form.get("no_shaft_info") == "true",
        "no_install_info": request.form.get("no_install_info") == "true",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "รอใบเสนอราคา"
    }

    file_fields = {
        'old_model_image': 'old_model_image_url',
        'motor_image': 'motor_image_url',
        'ratio_image': 'ratio_image_url',
        'install_image': 'install_image_url'
    }

    for field, url_key in file_fields.items():
        file = request.files.get(field)
        if file and file.filename:
            data[url_key] = upload_file_to_firebase(file, "uploads")

    # ====== สร้าง PDF และอัปโหลดเข้า Firebase ======
    pdf_path = generate_pdf(data)
    pdf_filename = os.path.basename(pdf_path)
    blob = bucket.blob(f"pdf/{pdf_filename}")
    blob.upload_from_filename(pdf_path)
    blob.make_public()
    data["pdf_url"] = blob.public_url

    ref.push(data)
    send_email_notification(data, attach_pdf_path=pdf_path)
    return redirect('/dashboard')

@app.route('/update_status/<quote_id>', methods=['POST'])
def update_status(quote_id):
    file = request.files.get("quotation_file")
    if not file or not file.filename:
        return "No file selected", 400

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        blob = bucket.blob(f"quotations/{filename}")
        blob.upload_from_filename(filepath)
        blob.make_public()

        ref.child(quote_id).update({
            "status": "ส่งแล้ว",
            "quotation_file_url": blob.public_url
        })

        return redirect('/dashboard')

    except Exception as e:
        return f"Error updating status: {str(e)}", 500

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)