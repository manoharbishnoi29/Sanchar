from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bakchodi-secret-key!'
socketio = SocketIO(app, cors_allowed_origins="*")

# मैसेज हिस्ट्री और ऑनलाइन यूज़र्स को स्टोर करने के लिए
chat_history = []
online_users = set()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    # नया यूज़र जुड़ने पर पुरानी चैट हिस्ट्री भेजें
    emit('load_history', chat_history)

@socketio.on('user_join')
def handle_user_join(username):
    if username:
        online_users.add(username)
        emit('update_online_count', len(online_users), broadcast=True)

@socketio.on('message')
def handle_message(data):
    username = data.get('username', 'User')
    message = data.get('message', '')
    time_str = datetime.now().strftime('%I:%M %p')
    
    msg_data = {
        'username': username,
        'message': message,
        'time': time_str,
        'avatar': f"https://api.dicebear.com/7.x/bottts/svg?seed={username}"  # हर यूज़र के नाम पर यूनिक अवतार
    }
    
    # हिस्ट्री में सेव करें (अधिकतम 100 मैसेज)
    chat_history.append(msg_data)
    if len(chat_history) > 100:
        chat_history.pop(0)

    emit('response_message', msg_data, broadcast=True)

@socketio.on('typing')
def handle_typing(data):
    emit('display_typing', data, broadcast=True, include_self=False)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
