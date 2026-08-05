import os
import sqlite3
import uuid
import hashlib
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
# Secret key from environment variable
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sanchar-default-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")

def init_db():
    conn = sqlite3.connect('sanchar.db')
    c = conn.cursor()
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (uid TEXT PRIMARY KEY, username TEXT UNIQUE, contact TEXT, password TEXT)''')
    # Messages Table (is_read column included)
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
        conn = sqlite3.connect('sanchar.db')
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
    
    conn = sqlite3.connect('sanchar.db')
    c = conn.cursor()
    c.execute("SELECT uid, username, contact FROM users WHERE username=? AND password=?", (username, hashed_pw))
    user = c.fetchone()
    conn.close()
    
    if user:
        return jsonify({'status': 'success', 'user': {'uid': user[0], 'username': user[1], 'contact': user[2]}})
    else:
        return jsonify({'status': 'error', 'message': 'गलत यूजरनेम या पासवर्ड!'})

# Get all users (Online + Offline) with unread message counts
@app.route('/api/users', methods=['GET'])
def get_users():
    current_uid = request.args.get('current_uid')
    conn = sqlite3.connect('sanchar.db')
    c = conn.cursor()
    c.execute("SELECT uid, username FROM users WHERE uid != ?", (current_uid,))
    users = c.fetchall()
    
    user_list = []
    for u in users:
        c.execute("SELECT COUNT(*) FROM messages WHERE sender_id=? AND receiver_id=? AND is_read=0", (u[0], current_uid))
        unread_count = c.fetchone()[0]
        user_list.append({'uid': u[0], 'username': u[1], 'unread': unread_count})
        
    conn.close()
    return jsonify({'status': 'success', 'users': user_list})

# Get chat history between two users and mark messages as read
@app.route('/api/messages', methods=['GET'])
def get_messages():
    sender_id = request.args.get('sender_id')
    receiver_id = request.args.get('receiver_id')
    
    conn = sqlite3.connect('sanchar.db')
    c = conn.cursor()
    
    c.execute("UPDATE messages SET is_read=1 WHERE sender_id=? AND receiver_id=?", (receiver_id, sender_id))
    conn.commit()
    
    c.execute("""SELECT sender_id, receiver_id, message, timestamp 
                 FROM messages 
                 WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?) 
                 ORDER BY id ASC""", (sender_id, receiver_id, receiver_id, sender_id))
    msgs = c.fetchall()
    conn.close()
    
    message_list = [{'sender_id': m[0], 'receiver_id': m[1], 'message': m[2], 'timestamp': m[3]} for m in msgs]
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
    
    conn = sqlite3.connect('sanchar.db')
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
    emit('receive_message', msg_data, room=sender_id)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
