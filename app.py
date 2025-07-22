from flask import Flask, render_template, request, redirect
from werkzeug.utils import secure_filename
import os
import tempfile
import firebase_admin
from firebase_admin import credentials, db, storage
from datetime import datetime
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from generate_pdf import generate_pdf

# Load env
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Init app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Firebase init
cred = credentials.Certificate("sas-transmission-firebase-adminsdk-fbsvc-964d6b7952.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://sas-transmission.asia-southeast1.firebasedatabase.app/',
    'storageBucket': 'sas-transmission.firebasestorage.app'
})
ref = db.reference("/quotations")
bucket = storage.bucket()

# upload helper
def upload_file_to_firebase(file, folder_name="uploads"):
    if file and file.filename:
        fname = secure_filename(file.filename)
        now = datetime.now().strftime('%Y%m%d_%H%M%S')
        blob = bucket.blob(f"{folder_name}/{now}_{fname}")
        blob.upload_from_file(file.stream, content_type=file.content_type)
        blob.make_public()
        return blob.public_url
    return ''

# email sender
def send_email_notification(data, attach_pdf_path=None, attach_extra_path=None):
    msg = EmailMessage()
    msg['Subject'] = '📨 ขอใบเสนอราคา SAS Transmission'
    product = data.get('product_type')
    # recipients
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
        to_list = [EMAIL_USER]; cc_list=[]
    msg['To'] = ', '.join(to_list)
    if cc_list: msg['Cc'] = ', '.join(cc_list)
    # body
    body = f"""
📌 Sale: {data.get('sale_name','-')}
📧 Email: {data.get('sale_email','-')}
👤 ลูกค้า: {data.get('customer_name','-')}
📞 โทร: {data.get('phone','-')}
🏢 บริษัท: {data.get('company','-')}
📦 สินค้า: {product}
🎯 วัตถุประสงค์: {data.get('purpose','-')}
🚀 ความเร่งด่วน: {data.get('quotation_speed','-')}
📅 ส่งเมื่อ: {data.get('timestamp','-')}
"""
    msg.set_content(body)
    # attach pdf
    if attach_pdf_path and os.path.exists(attach_pdf_path):
        with open(attach_pdf_path,'rb') as f:
            msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=os.path.basename(attach_pdf_path))
    # attach extra
    if attach_extra_path and os.path.exists(attach_extra_path):
        ext = os.path.splitext(attach_extra_path)[1].lower()
        subtype = 'pdf' if ext=='.pdf' else 'vnd.ms-excel'
        with open(attach_extra_path,'rb') as f:
            msg.add_attachment(f.read(), maintype='application', subtype=subtype, filename=os.path.basename(attach_extra_path))
    # send
    try:
        with smtplib.SMTP('smtp.gmail.com',587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
    except Exception as e:
        print('❌ Error sending email:', e)

# routes
@app.route('/')
def index(): return render_template('index.html')
@app.route('/form')
def form(): return render_template('request_form.html')
@app.route('/dashboard')
def dashboard():
    qs = ref.get() or {}
    sd = sorted(qs.items(), key=lambda x:x[1]['timestamp'], reverse=True)
    return render_template('dashboard.html',quotations=sd)

@app.route('/submit',methods=['POST'])
def submit():
    try:
        data={
            'sale_name':request.form['sale_name'],
            'sale_email':request.form['sale_email'],
            'customer_name':request.form['customer_name'],
            'phone':request.form['customer_phone'],
            'company':request.form['customer_company'],
            'product_type':request.form['product_type'],
            'purpose':request.form.get('purpose',''),
            'quotation_speed':request.form['quotation_speed'],
            'timestamp':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status':'รอใบเสนอราคา'
        }
        attach_pdf=None; attach_extra=None
        if data['product_type']=='Gear Motor':
            pdf=generate_pdf(data)
            pblob=bucket.blob(f"pdf/{os.path.basename(pdf)}")
            pblob.upload_from_filename(pdf); pblob.make_public()
            data['pdf_url']=pblob.public_url; attach_pdf=pdf
        else:
            extra=request.files.get('extra_file')
            local=os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(extra.filename))
            extra.save(local)
            data['attachment_url']=upload_file_to_firebase(extra,'attachments')
            attach_extra=local
        # handle replace images
        if data.get('purpose')=='วางแทนของเดิม':
            for fld,key in {'old_model_image':'old_model_image_url','motor_image':'motor_image_url','ratio_image':'ratio_image_url','install_image':'install_image_url'}.items():
                f=request.files.get(fld)
                local_img=os.path.join(app.config['UPLOAD_FOLDER'],secure_filename(f.filename))
                f.save(local_img)
                data[key]=upload_file_to_firebase(f,'uploads')
                # optionally attach images
        ref.push(data)
        send_email_notification(data,attach_pdf_path=attach_pdf,attach_extra_path=attach_extra)
        return redirect('/dashboard')
    except Exception as e:
        return f"Error: {e}",500

@app.route('/update_status/<quote_id>',methods=['POST'])
def update_status(quote_id):
    # ... unchanged ...
    return redirect('/dashboard')

if __name__=='__main__':
    app.run(debug=True)
