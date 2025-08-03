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

# Load environment
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Firebase
cred = credentials.Certificate("sas-transmission-firebase-adminsdk-fbsvc-964d6b7952.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://sas-transmission.asia-southeast1.firebasedatabase.app/',
    'storageBucket': 'sas-transmission.firebasestorage.app'
})
ref = db.reference("/quotations")
bucket = storage.bucket()

# Helper: upload file to Firebase Storage
def upload_file_to_firebase(file, folder_name="uploads"):
    if file and file.filename:
        # Reset stream position to beginning before uploading
        try:
            file.stream.seek(0)
        except Exception:
            pass
        fname = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        blob = bucket.blob(f"{folder_name}/{timestamp}_{fname}")
        blob.upload_from_file(file.stream, content_type=file.content_type)
        blob.make_public()
        return blob.public_url
    return ''

# Send email with optional attachments
def send_email_notification(data, attach_pdf_path=None, attach_extra_path=None, attach_images=None):
    msg = EmailMessage()
    product = data.get('product_type')
    msg['Subject'] = f"📨 ขอใบเสนอราคา ({product})"

    # Determine recipients based on product
    if product == 'Gear Motor':
        to_list = ['Somyot@synergy-as.com']
        cc_list = ['sas04@synergy-as.com','sas06@synergy-as.com','kongkiat@synergy-as.com','traiwit@synergy-as.com']
    elif product == 'Conveyor & Automation':
        to_list = ['matinee@synergy-as.com','wiroj@synergy-as.com','Somyot@synergy-as.com']
        cc_list = ['sas07@synergy-as.com','sas06@synergy-as.com','kongkiat@synergy-as.com','traiwit@synergy-as.com']
    elif product == 'Structure':
        to_list = ['design_pp@hotmail.com','designsas2024@gmail.com','tanin@synergy-as.com','Sukitkongprom@gmail.com','SAS03@synergy-as.com','sas04@synergy-as.com']
        cc_list = ['design_pp@hotmail.com','designsas2024@gmail.com','tanin@synergy-as.com','Sukitkongprom@gmail.com','SAS03@synergy-as.com','sas07@synergy-as.com','sas06@synergy-as.com','kongkiat@synergy-as.com','traiwit@synergy-as.com','sassynergy2024@outlook.com']
    else:
        to_list = [EMAIL_USER]
        cc_list = []

    msg['To'] = ', '.join(to_list)
    if cc_list:
        msg['Cc'] = ', '.join(cc_list)

    # Email body
    body = f"""
📌 Sale: {data.get('sale_name','-')}
📧 Sale Email: {data.get('sale_email','-')}
👤 ลูกค้า: {data.get('customer_name','-')}
📞 โทร: {data.get('phone','-')}
🏢 บริษัท: {data.get('company','-')}
📦 สินค้า: {product}
🎯 วัตถุประสงค์: {data.get('purpose','-')}
🔧 Model/Unit: {data.get('motor_model','-')} / {data.get('motor_unit','-')}
⚙️ อัตราทด: {data.get('ratio','-')}
🔌 Controller: {data.get('controller','-')}
📝 ข้อมูลอื่นๆ: {data.get('other_info','-')}
🚀 ความเร่งด่วน: {data.get('quotation_speed','-')}
📅 ส่งเมื่อ: {data.get('timestamp','-')}
"""
    msg.set_content(body)

    # Attach PDF
    if attach_pdf_path and os.path.exists(attach_pdf_path):
        with open(attach_pdf_path, 'rb') as f:
            msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=os.path.basename(attach_pdf_path))

    # Attach extra file (Excel/PDF)
    if attach_extra_path and os.path.exists(attach_extra_path):
        ext = os.path.splitext(attach_extra_path)[1].lower()
        subtype = 'pdf' if ext == '.pdf' else 'vnd.ms-excel'
        with open(attach_extra_path, 'rb') as f:
            msg.add_attachment(f.read(), maintype='application', subtype=subtype, filename=os.path.basename(attach_extra_path))

    # Attach images from replace scenario
    if attach_images:
        for img_path in attach_images:
            if os.path.exists(img_path):
                ext = os.path.splitext(img_path)[1].lower().strip('.')
                maintype = 'image'
                subtype = 'jpeg' if ext in ['jpg','jpeg'] else ext
                with open(img_path, 'rb') as f:
                    msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(img_path))

    # Send via SMTP
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
    except Exception as e:
        print('❌ Error sending email:', e)

# Routes
@app.route('/')
def index(): return render_template('index.html')
@app.route('/form')
def form(): return render_template('request_form.html')
@app.route('/dashboard')
def dashboard():
    quotations = ref.get() or {}
    sorted_data = sorted(quotations.items(), key=lambda x: x[1]['timestamp'], reverse=True)
    return render_template('dashboard.html', quotations=sorted_data)

def generate_job_number(product_type, queue_number):
    today = datetime.now().strftime("%d%m%y")  # เช่น 150868
    prefix_map = {
        'Gear Motor': 'GEA',
        'Conveyor & Automation': 'AUT',
        'Structure': 'STC'
    }
    code = prefix_map.get(product_type, 'XXX')
    return f"SAS{code}{today}{str(queue_number).zfill(3)}"


@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = {
	    all_quotes = ref.get() or {}
            queue_number = len(all_quotes) + 1
            'sale_name': request.form.get('sale_name'),
            'sale_email': request.form.get('sale_email'),
            'customer_name': request.form.get('customer_name'),
            'phone': request.form.get('customer_phone'),
            'company': request.form.get('customer_company'),
            'product_type': request.form.get('product_type'),
	        'job_number': generate_job_number(request.form.get('product_type'), queue_number),
            'purpose': request.form.get('purpose',''),
            'motor_model': request.form.get('motor_model',''),
            'motor_unit': request.form.get('motor_unit',''),
            'ratio': request.form.get('gear_ratio',''),
            'controller': request.form.get('controller',''),
            'other_info': request.form.get('other_info',''),
            'quotation_speed': request.form.get('quotation_speed'),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'รอใบเสนอราคา'
        }

        attach_pdf = None
        attach_extra = None
        attach_images = []

        # If Gear Motor selected -> ALWAYS generate PDF regardless of purpose
        if data['product_type'] == 'Gear Motor':
            pdf_path = generate_pdf(data)
            blob = bucket.blob(f"pdf/{os.path.basename(pdf_path)}")
            blob.upload_from_filename(pdf_path)
            blob.make_public()
            data['pdf_url'] = blob.public_url
            attach_pdf = pdf_path
        else:
            # Conveyor & Automation or Structure: handle extra file
            extra = request.files.get('extra_file')
            local_extra = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(extra.filename))
            extra.save(local_extra)
            data['attachment_url'] = upload_file_to_firebase(extra, 'attachments')
            attach_extra = local_extra

        # If replacing old machine: upload images and collect paths
        if data.get('purpose') == 'วางแทนของเดิม':
            image_fields = ['old_model_image','motor_image','ratio_image','install_image']
            for fld in image_fields:
                img = request.files.get(fld)
                if img and img.filename:
                    local_img = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(img.filename))
                    img.save(local_img)
                    data[f"{fld}_url"] = upload_file_to_firebase(img, 'uploads')
                    attach_images.append(local_img)

        # Push to Firebase
        ref.push(data)
        # Send email with all attachments
        send_email_notification(data, attach_pdf_path=attach_pdf, attach_extra_path=attach_extra, attach_images=attach_images)
        return redirect('/dashboard')
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/update_status/<quote_id>', methods=['POST'])
def update_status(quote_id):
    # existing update_status logic unchanged
    return redirect('/dashboard')

if __name__ == '__main__':
    app.run(debug=True)