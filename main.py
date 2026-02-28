import os
import re
import asyncio
import base64
import edge_tts
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # क्रॉस-ओरिजिन रिक्वेस्ट (Blogger से) को अनुमति देने के लिए

def sanitize_and_format_text(text):
    # 1. Ultra-Clean Text: फालतू सजावटी चिन्ह हटाना
    text = re.sub(r'[\~\*_\#\@\^&\|<>]', '', text)
    
    # इमोजी हटाना (Unicode Range for Emojis)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    
    # 2. List & Table Handling: बुलेट पॉइंट्स और टेबल को नेचुरल पॉज़ में बदलना
    # लिस्ट आइटम्स (-, •, 1.) के बाद फुलस्टॉप (.) लगाना ताकि AI रुके
    text = re.sub(r'\n\s*[-•]\s+', '.\n', text) 
    text = re.sub(r'\n\s*\d+\.\s+', '.\n', text)
    
    # टेबल्स (Tabs या ज्यादा स्पेस) को कॉमा में बदलना
    text = re.sub(r'\t+', ', ', text)
    text = re.sub(r' {2,}', ' ', text)
    
    return text.strip()

async def generate_audio_and_boundaries(text, voice):
    communicate = edge_tts.Communicate(text, voice)
    audio_data = b""
    word_boundaries =[]
    
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
        elif chunk["type"] == "WordBoundary":
            # Edge-TTS टाइमिंग 'ticks' (100-ns) में देता है, इसे Milliseconds में बदलना
            word_boundaries.append({
                "text": chunk["text"],
                "offset": chunk["offset"] / 10000, 
                "duration": chunk["duration"] / 10000
            })
            
    return audio_data, word_boundaries

@app.route('/generate-tts', methods=['POST'])
def generate_tts():
    try:
        data = request.json
        raw_text = data.get('text', '')
        voice = data.get('voice', 'hi-IN-SwaraNeural') # Default: Female
        
        # टेक्स्ट सैनिटाइजेशन
        clean_text = sanitize_and_format_text(raw_text)
        
        if not clean_text:
            return jsonify({"error": "No valid text provided"}), 400

        # Async टास्क को Flask में चलाना
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_bytes, boundaries = loop.run_until_complete(generate_audio_and_boundaries(clean_text, voice))
        
        # ऑडियो को Base64 में भेजना ताकि सीधे प्ले हो सके
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        return jsonify({
            "status": "success",
            "audio_base64": audio_b64,
            "boundaries": boundaries,
            "clean_text": clean_text
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Hosting Ready: Render/Koyeb के लिए पोर्ट कॉन्फ़िगरेशन
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
