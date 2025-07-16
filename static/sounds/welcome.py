import edge_tts
import asyncio

async def generate_voice():
    text = "ยินดีต้อนรับ ขอให้วันนี้เป็นวันที่ดี มีความสุขกับการขายมอเตอร์เกียร์ SAS นะคะ"
    voice = "th-TH-PremwadeeNeural"  # เสียงผู้หญิงไทยที่เหมือนคนจริงมาก
    output_path = "welcome.mp3"

    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(output_path)
    print("✅ เสียงถูกสร้างและบันทึกเป็น welcome.mp3")

asyncio.run(generate_voice())
