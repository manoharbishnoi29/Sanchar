from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
from datetime import datetime
import sqlite3
import uuid
import hashlib

app = Flask(__name__)
import os
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-default-key-for-local')

socketio = SocketIO(app, cors_allowed_origins="*")

# Database Setup
def init_db():
    conn = sqlite3.connect('sanchar.db')
    c = conn.cursor()
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    uid TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    contact TEXT NOT NULL,
                    password TEXT NOT NULL
                )''')
    # Messages Table
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )''')
    conn.commit()
    conn.close()

init_db()

def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Online users tracking
online_users = {} # {username: sid}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username', '').strip()
    contact = data.get('contact', '').strip() # Email or Mobile
    password = data.get('password', '').strip()

    if not username or not contact or not password:
        return jsonify({'success': False, 'message': 'सभी फ़ील्ड्स भरना अनिवार्य है!'})

    conn = sqlite3.connect('sanchar.db')
    c = conn.cursor()
    
    # Check if username exists
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'message': 'यह Username पहले से इस्तेमाल में है!'})

    uid = f"UID-{uuid.uuid4().hex[:8].upper()}"
    hashed_p = hash_pass(password)
    
    c.execute('INSERT INTO users VALUES (?, ?, ?, ?)', (uid, username, contact, hashed_p))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'uid': uid, 'username': username})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    conn = sqlite3.connect('sanchar.db')
    c = conn.cursor()
    c.execute('SELECT uid, username FROM users WHERE username = ? AND password = ?', (username, hash_pass(password)))
    user = c.fetchone()
    conn.close()

    if user:
        return jsonify({'success': True, 'uid': user[0], 'username': user[1]})
    else:
        return jsonify({'success': False, 'message': 'गलत Username या Password!'})

@app.route('/api/messages/<user1>/<user2>', methods=['GET'])
def get_chat_history(user1, user2):
    conn = sqlite3.connect('sanchar.db')
    c = conn.cursor()
    c.execute('''SELECT sender, recipient, message, timestamp FROM messages 
                 WHERE (sender = ? AND recipient = ?) OR (sender = ? AND recipient = ?)
                 ORDER BY id ASC''', (user1, user2, user2, user1))
    rows = c.fetchall()
    conn.close()
    
    msgs = [{'sender': r[0], 'recipient': r[1], 'message': r[2], 'time': r[3]} for r in rows]
    return jsonify({'success': True, 'messages': msgs})

# SocketIO Events
@socketio.on('register_user')
def handle_register(username):
    online_users[username] = request.sid
    emit('update_user_list', list(online_users.keys()), broadcast=True)

@socketio.on('private_message')
def handle_private_message(data):
    sender = data.get('sender')
    recipient = data.get('recipient')
    message = data.get('message')
    time_str = datetime.now().strftime('%I:%M %p')

    # Save to Database
    conn = sqlite3.connect('sanchar.db')
    c = conn.cursor()
    c.execute('INSERT INTO messages (sender, recipient, message, timestamp) VALUES (?, ?, ?, ?)', 
              (sender, recipient, message, time_str))
    conn.commit()
    conn.close()

    payload = {'sender': sender, 'recipient': recipient, 'message': message, 'time': time_str}
    recipient_sid = online_users.get(recipient)
    
    if recipient_sid:
        emit('receive_private_message', payload, room=recipient_sid)
    emit('receive_private_message', payload, room=request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    for user, sid in list(online_users.items()):
        if sid == request.sid:
            del online_users[user]
            break
    emit('update_user_list', list(online_users.keys()), broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
