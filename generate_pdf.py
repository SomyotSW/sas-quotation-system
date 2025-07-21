from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
import tempfile
import requests
from PIL import Image
from io import BytesIO
import os

# ลงทะเบียนฟอนต์ไทย
pdfmetrics.registerFont(TTFont('THSarabunNew', 'static/fonts/THSarabunNew.ttf'))

def generate_pdf(data):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(temp_file.name, pagesize=A4)
    width, height = A4
    c.setFont("THSarabunNew", 16)

    def draw_text(label, value, y):
        c.drawString(2 * cm, y, f"{label}: {value}")
        return y - 1.2 * cm

    y = height - 2 * cm
    c.setFont("THSarabunNew", 22)
    c.drawString(2 * cm, y, "📌 รายการขอใบเสนอราคาจาก Sale")
    y -= 2 * cm

    # ==== ข้อมูลใบเสนอราคา ====
    y = draw_text("Speed Controller / Driver", data.get("controller", ""), y)
    y = draw_text("อัตราทด", data.get("ratio", ""), y)
    y = draw_text("Model ที่ต้องการ", data.get("motor_model", ""), y)
    y = draw_text("หน่วย (W/HP/kW)", data.get("motor_unit", ""), y)
    y = draw_text("ข้อมูลจำเป็นอื่น ๆ", data.get("other_info", ""), y)
    y = draw_text("ประเภทใบเสนอราคา", data.get("quotation_speed", ""), y)
    y -= 1 * cm

    # ==== ข้อมูลลูกค้า / เซลล์ ====
    y = draw_text("ชื่อเซลล์", data.get("sale_name", ""), y)
    y = draw_text("อีเมลเซลล์", data.get("sale_email", ""), y)
    y = draw_text("ชื่อลูกค้า", data.get("customer_name", ""), y)
    y = draw_text("เบอร์โทร", data.get("phone", ""), y)
    y = draw_text("บริษัทลูกค้า", data.get("company", ""), y)
    y = draw_text("วัตถุประสงค์", data.get("purpose", ""), y)
    y = draw_text("วันที่ส่งข้อมูล", data.get("timestamp", ""), y)
    y -= 1 * cm

    # ==== แนบรูปภาพ ====
    def draw_image_from_url(url, label, y):
        try:
            response = requests.get(url)
            img = Image.open(BytesIO(response.content))
            img = ImageReader(img)
            c.drawString(2 * cm, y, label)
            y -= 0.7 * cm
            c.drawImage(img, 2 * cm, y - 6 * cm, width=6 * cm, height=6 * cm, preserveAspectRatio=True)
            return y - 6.5 * cm
        except Exception as e:
            c.drawString(2 * cm, y, f"{label} - แนบไม่ได้")
            return y - 1 * cm

    img_fields = {
        "old_model_image_url": "รูป: Old Model",
        "motor_image_url": "รูป: Motor",
        "ratio_image_url": "รูป: Ratio",
        "install_image_url": "รูป: Install"
    }

    for key, label in img_fields.items():
        if key in data and data[key]:
            y = draw_image_from_url(data[key], label, y)
            if y < 5 * cm:
                c.showPage()
                c.setFont("THSarabunNew", 16)
                y = height - 2 * cm

    c.save()
    return temp_file.name