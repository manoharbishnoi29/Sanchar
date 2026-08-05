from flask import Flask, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sanchar-secret-key!'
socketio = SocketIO(app, cors_allowed_origins="*")

# ऑनलाइन यूज़र्स और उनके सॉकेट आईडी (socket.id)
users = {} # {username: sid}
user_sids = {} # {sid: username}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('register_user')
def handle_register(username):
    from flask import request
    users[username] = request.sid
    user_sids[request.sid] = username
    
    # सभी को अपडेटेड ऑनलाइन यूज़र लिस्ट भेजें
    emit('update_user_list', list(users.keys()), broadcast=True)

@socketio.on('private_message')
def handle_private_message(data):
    from flask import request
    sender = user_sids.get(request.sid)
    recipient = data.get('recipient')
    message = data.get('message')
    time_str = datetime.now().strftime('%I:%M %p')

    recipient_sid = users.get(recipient)
    
    payload = {
        'sender': sender,
        'recipient': recipient,
        'message': message,
        'time': time_str
    }

    # मैसेज सिर्फ प्राप्तकर्ता (Recipient) और भेजने वाले (Sender) को दिखेगा
    if recipient_sid:
        emit('receive_private_message', payload, room=recipient_sid)
    emit('receive_private_message', payload, room=request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    from flask import request
    sid = request.sid
    if sid in user_sids:
        username = user_sids[sid]
        del user_sids[sid]
        if username in users:
            del users[username]
        emit('update_user_list', list(users.keys()), broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
  
