from flask import Flask, request, send_file
from flask_cors import CORS
from typecast import Typecast
from typecast.models import TTSRequest, SmartPrompt, Output, VoicesV2Filter
from typecast.models import GenderEnum, TTSModel
import io

app = Flask(__name__)
CORS(app)

API_KEY = "__pltXpYoTLWjRV3KUshUysP4Qqa9McPHL6EZpC5Yz8YF"
client = Typecast(api_key=API_KEY)

@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json()

    if not data:
        return "No data", 400

    text = data.get("text")

    if not text:
        return "No text", 400

    print("✅ 받은 텍스트:", text)

    try:
        # ✅ 여성 목소리 자동 선택 (핵심🔥)
        voices = client.voices_v2(
            VoicesV2Filter(
                model=TTSModel.SSFM_V30,
                gender=GenderEnum.FEMALE
            )
        )

        voice_id = voices[0].voice_id  # ✅ 첫 번째 여성 voice

        print("✅ 선택된 voice:", voices[0].voice_name)

        response = client.text_to_speech(
            TTSRequest(
                text=text,
                model="ssfm-v30",
                voice_id=voice_id,

                # ✅ 자연스럽고 친절한 톤
                prompt=SmartPrompt(
                    emotion_type="smart"
                ),

                output=Output(
                    audio_format="mp3",
                    audio_tempo=1.0,   # ✅ 고객센터 속도
                    audio_pitch=-1      # ✅ 살짝 밝게 (중요🔥)
                )
            )
        )

        return send_file(
            io.BytesIO(response.audio_data),
            mimetype="audio/mpeg"
        )

    except Exception as e:
        print("❌ 오류:", e)
        return "TTS error", 500


if __name__ == "__main__":
    app.run(debug=True)