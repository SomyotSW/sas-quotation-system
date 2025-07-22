import edge_tts
import asyncio

async def generate_voice():
    text = "รายละเอียดถูกจัดส่งเรียบร้อย กรุณารอสักครู่ และขอให้ท่านเฮงๆๆ ปังๆๆ กับการขายสินค้าของเรานะคะ"
    voice = "th-TH-PremwadeeNeural"  # เสียงผู้หญิงไทยที่เหมือนคนจริงมาก
    output_path = "success.mp3"

    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(output_path)
    print("✅ เสียงถูกสร้างและบันทึกเป็น success.mp3")

asyncio.run(generate_voice())
