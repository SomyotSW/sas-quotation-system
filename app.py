from flask import Flask, render_template, request, redirect
from werkzeug.utils import secure_filename
import os
import firebase_admin
from firebase_admin import credentials, db, storage
import datetime
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Firebase setup
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://sas-transmission.firebaseio.com/',
    'storageBucket': 'sas-transmission.appspot.com'
})

ref = db.reference("/quotations")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/request')
def request_list():
    try:
        quotations = ref.get()
        if quotations:
            sorted_data = sorted(quotations.items(), key=lambda x: x[1]['timestamp'], reverse=True)
        else:
            sorted_data = []
        return render_template('dashboard.html', quotations=sorted_data)
    except Exception as e:
        return f"Error loading data: {str(e)}"

@app.route('/submit', methods=['POST'])
def submit():
    data = {
        "sale_name": request.form.get("sale_name"),
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
        "status": "รอใบเสนอราคา",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Upload optional files
    bucket = storage.bucket()
    file_fields = {
        'old_model_image': 'old_model_image_url',
        'motor_image': 'motor_image_url',
        'ratio_image': 'ratio_image_url',
        'install_image': 'install_image_url'
    }

    for field, url_key in file_fields.items():
        file = request.files.get(field)
        if file and file.filename:
            filename = secure_filename(file.filename)
            blob = bucket.blob(f"uploads/{filename}")
            blob.upload_from_file(file)
            blob.make_public()
            data[url_key] = blob.public_url

    # Save to Firebase
    new_ref = ref.push(data)

    # Email Notification
    send_email_notification(data)

    return redirect('/request')

@app.route('/update_status/<quote_id>', methods=['POST'])
def update_status(quote_id):
    file = request.files.get("quotation_file")
    if file and file.filename:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        blob = storage.bucket().blob(f"quotations/{filename}")
        blob.upload_from_filename(filepath)
        blob.make_public()

        ref.child(quote_id).update({
            "status": "ส่งแล้ว",
            "quotation_file_url": blob.public_url
        })

    return redirect('/request')

def send_email_notification(data):
    msg = EmailMessage()
    msg['Subject'] = '📨 มีการขอใบเสนอราคาใหม่จาก Sale'
    msg['From'] = "noreply@motorsas.com"
    msg['To'] = "Somyot@synergy-as.com"
    msg['Cc'] = "traiwit@synergy-as.com, kongkiat@synergy-as.com"

    content = f"""
    📌 Sale: {data['sale_name']}
    👤 ลูกค้า: {data['customer_name']}
    📞 เบอร์: {data['phone']}
    🏢 บริษัท: {data['company']}
    🎯 วัตถุประสงค์: {data['purpose']}
    📅 เวลา: {data['timestamp']}
    """
    msg.set_content(content)

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login("Somyotsw442@gmail.com", "dfwj earf bvuj jcrv")  # คุณสามารถเปลี่ยนมาใช้ตัวแปร env หรือ secrets ใน production
            smtp.send_message(msg)
    except Exception as e:
        print("Error sending email:", e)

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)