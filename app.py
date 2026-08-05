import os
import sqlite3
import uuid
import hashlib
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sanchar-secret-key-2026')
socketio = SocketIO(app, cors_allowed_origins="*")

# SQLite Database Setup
DB_PATH = os.path.join(os.path.dirname(__file__), 'sanchar.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (uid TEXT PRIMARY KEY, username TEXT UNIQUE, contact TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  sender_id TEXT, 
                  receiver_id TEXT, 
                  message TEXT, 
                  timestamp TEXT,
                  is_read INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    contact = data.get('contact')
    password = data.get('password')
    
    if not username or not contact or not password:
        return jsonify({'status': 'error', 'message': 'सभी फील्ड भरना जरूरी है!'})
        
    hashed_pw = hash_password(password)
    user_id = str(uuid.uuid4())[:8]
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user_id, username, contact, hashed_pw))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'user': {'uid': user_id, 'username': username, 'contact': contact}})
    except sqlite3.IntegrityError:
        return jsonify({'status': 'error', 'message': 'यह यूजरनेम पहले से मौजूद है!'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    hashed_pw = hash_password(password)
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT uid, username, contact FROM users WHERE username=? AND password=?", (username, hashed_pw))
    user = c.fetchone()
    conn.close()
    
    if user:
        return jsonify({'status': 'success', 'user': {'uid': user['uid'], 'username': user['username'], 'contact': user['contact']}})
    else:
        return jsonify({'status': 'error', 'message': 'गलत यूजरनेम या पासवर्ड!'})

@app.route('/api/users', methods=['GET'])
def get_users():
    current_uid = request.args.get('current_uid')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT uid, username FROM users WHERE uid != ?", (current_uid,))
    users = c.fetchall()
    
    user_list = []
    for u in users:
        c.execute("SELECT COUNT(*) as unread FROM messages WHERE sender_id=? AND receiver_id=? AND is_read=0", (u['uid'], current_uid))
        unread_count = c.fetchone()['unread']
        user_list.append({'uid': u['uid'], 'username': u['username'], 'unread': unread_count})
        
    conn.close()
    return jsonify({'status': 'success', 'users': user_list})

@app.route('/api/messages', methods=['GET'])
def get_messages():
    sender_id = request.args.get('sender_id')
    receiver_id = request.args.get('receiver_id')
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE messages SET is_read=1 WHERE sender_id=? AND receiver_id=?", (receiver_id, sender_id))
    conn.commit()
    
    c.execute("""SELECT sender_id, receiver_id, message, timestamp 
                 FROM messages 
                 WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?) 
                 ORDER BY id ASC""", (sender_id, receiver_id, receiver_id, sender_id))
    msgs = c.fetchall()
    conn.close()
    
    message_list = [{'sender_id': m['sender_id'], 'receiver_id': m['receiver_id'], 'message': m['message'], 'timestamp': m['timestamp']} for m in msgs]
    return jsonify({'status': 'success', 'messages': message_list})

@socketio.on('join')
def on_join(data):
    user_id = data.get('user_id')
    if user_id:
        join_room(user_id)

@socketio.on('private_message')
def handle_private_message(data):
    sender_id = data['sender_id']
    receiver_id = data['receiver_id']
    message = data['message']
    timestamp = datetime.now().strftime("%I:%M %p")
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO messages (sender_id, receiver_id, message, timestamp, is_read) VALUES (?, ?, ?, ?, 0)",
              (sender_id, receiver_id, message, timestamp))
    conn.commit()
    conn.close()
    
    msg_data = {
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'message': message,
        'timestamp': timestamp
    }
    
    emit('receive_message', msg_data, room=receiver_id)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
