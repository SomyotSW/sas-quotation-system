from flask import Flask, render_template, request, redirect
from werkzeug.utils import secure_filename
import os
import firebase_admin
from firebase_admin import credentials, db, storage
import datetime
from datetime import datetime
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from generate_pdf import generate_pdf  # ฟังก์ชันสร้าง PDF

# ===== โหลด ENV (.env) =====
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# ===== Firebase setup =====
print("📦 Initializing Firebase...")
cred = credentials.Certificate("sas-transmission-firebase-adminsdk-fbsvc-964d6b7952.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://sas-transmission.asia-southeast1.firebasedatabase.app/',
    'storageBucket': 'sas-transmission.appspot.com'
})
ref = db.reference("/quotations")
bucket = storage.bucket()
print("✅ Firebase Initialized.")

# ===== Upload File =====
def upload_file_to_firebase(file, folder_name="uploads"):
    if file and file.filename:
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
        blob = bucket.blob(f"{folder_name}/{filename}")
        blob.upload_from_file(file.stream, content_type=file.content_type)
        blob.make_public()
        print(f"🖼️ Uploaded {filename} to Firebase: {blob.public_url}")
        return blob.public_url
    return ''

# ===== Email Sender =====
def send_email_notification(data, attach_pdf_path=None):
    msg = EmailMessage()
    msg['Subject'] = '📨 ขอใบเสนอราคา SAS Transmission'
    msg['From'] = EMAIL_USER
    msg['To'] = "Somyot@synergy-as.com"
    msg['Cc'] = "sas04@synergy-as.com","sas06@synergy-as.com"

    content = f"""
📌 ชื่อเซลล์: {data.get('sale_name', '-')}
📧 อีเมลเซลล์: {data.get('sale_email', '-')}
👤 ชื่อลูกค้า: {data.get('customer_name', '-')}
📞 เบอร์โทรลูกค้า: {data.get('phone', '-')}
🏢 บริษัทลูกค้า: {data.get('company', '-')}
🎯 วัตถุประสงค์: {data.get('purpose', '-')}
🚀 ความเร่งด่วน: {data.get('quotation_speed', '-')}
📅 เวลาที่ส่ง: {data.get('timestamp', '-')}

🔗 ลิงก์ไฟล์ PDF: {data.get('pdf_url', '-')}
    """
    msg.set_content(content)

    if attach_pdf_path:
        with open(attach_pdf_path, 'rb') as f:
            msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=os.path.basename(attach_pdf_path))

    try:
        print("📧 Connecting to Gmail SMTP...")
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print("✅ Email sent successfully.")
    except Exception as e:
        print("❌ Error sending email:", e)

# ===== Routes =====
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
        print("📊 Loaded data from Firebase.")
        sorted_data = sorted(quotations.items(), key=lambda x: x[1]['timestamp'], reverse=True) if quotations else []
        return render_template('dashboard.html', quotations=sorted_data)
    except Exception as e:
        print("❌ Error loading dashboard:", e)
        return f"Error loading dashboard: {str(e)}"

@app.route('/submit', methods=['POST'])
def submit():
    try:
        print("\n🟢 ==== [START] /submit ==== 🟢")
        print("📥 Form Data:", request.form)
        print("📎 Files:", request.files)

        data = {
            "sale_name": request.form.get("sale_name"),
            "sale_email": request.form.get("sale_email"),
            "customer_name": request.form.get("customer_name"),
            "phone": request.form.get("customer_phone"),
            "company": request.form.get("customer_company"),
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

        # ==== Upload Images ====
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

        # ==== Generate PDF ====
        pdf_path = generate_pdf(data)
        print(f"📄 PDF Generated: {pdf_path}")
        pdf_filename = os.path.basename(pdf_path)
        blob = bucket.blob(f"pdf/{pdf_filename}")
        blob.upload_from_filename(pdf_path)
        blob.make_public()
        data["pdf_url"] = blob.public_url
        print(f"✅ PDF Uploaded to Firebase: {data['pdf_url']}")

        # ==== Save to Firebase DB ====
        ref.push(data)
        print("✅ Data pushed to Firebase Realtime DB.")

        # ==== Send Email ====
        send_email_notification(data, attach_pdf_path=pdf_path)

        print("🟢 ==== [END] /submit ==== 🟢\n")
        return redirect('/dashboard')

    except Exception as e:
        print("❌ ERROR in /submit:", e)
        return f"Error: {e}", 500

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
        print("❌ Error updating status:", e)
        return f"Error updating status: {str(e)}", 500

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    print("🚀 Starting Flask server...")
    app.run(debug=True)