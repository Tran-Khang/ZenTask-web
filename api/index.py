import os
import json
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
import uuid
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

USERS_FILE = 'users.json'

# Cấu hình upload
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Tạo thư mục upload nếu chưa tồn tại
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}

def save_users(users):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        return True
    except IOError:
        return False

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        if username in users and users[username]['password'] == password:
            session['username'] = username
            return redirect(url_for('dashboard'))
        error = "Tên đăng nhập hoặc mật khẩu không đúng"
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        if username in users:
            error = "Tên đăng nhập đã tồn tại"
        else:
            users[username] = {
                'password': password,
                'pomodoros': [25, 30, 45],
                'flashcards': []  # Thêm mảng flashcards rỗng
            }
            if save_users(users):
                session['username'] = username
                return redirect(url_for('dashboard'))
            error = "Lỗi khi lưu dữ liệu"
    return render_template('register.html', error=error)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    users = load_users()
    user_data = users.get(username, {})
    pomodoros = user_data.get('pomodoros', [])
    
    if request.method == 'POST':
        new_pomo = request.form.get('new_pomodoro')
        if new_pomo:
            try:
                minutes = int(new_pomo)
                pomodoros.append(minutes)
                user_data['pomodoros'] = pomodoros
                users[username] = user_data
                save_users(users)
            except ValueError:
                pass
        return redirect(url_for('dashboard'))
    
    return render_template('dashboard.html', 
                          username=username, 
                          pomodoros=pomodoros)

@app.route('/pomodoro')
def pomodoro():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    selected = request.args.get('selected')
    if selected:
        try:
            minutes = int(selected)
            return render_template('pomodoro.html', minutes=minutes)
        except ValueError:
            pass
    return redirect(url_for('dashboard'))

@app.route('/flashcards')
def flashcards():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    users = load_users()
    user_data = users.get(username, {})
    # Lấy flashcard từ dữ liệu người dùng thay vì dữ liệu cứng
    flashcards_data = user_data.get('flashcards', [])
    return render_template('flashcards.html', flashcards=flashcards_data)

@app.route('/study_flashcards')
def study_flashcards():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    users = load_users()
    user_data = users.get(username, {})
    flashcards = user_data.get('flashcards', [])
    
    # Đảm bảo mỗi flashcard có ID
    for i, card in enumerate(flashcards):
        card['id'] = i + 1
    
    return render_template('flashcard_study.html', flashcards=flashcards)

# THÊM ROUTE MỚI CHO FLASHCARD
@app.route('/add_flashcard', methods=['POST'])
def add_flashcard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    users = load_users()
    user_data = users.get(username, {})
    
    # Lấy dữ liệu từ form
    question = request.form['question']
    answer = request.form['answer']
    
    # Xử lý upload file
    image_filename = None
    if 'image' in request.files:
        file = request.files['image']
        if file.filename != '' and allowed_file(file.filename):
            # Tạo tên file duy nhất
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            image_filename = unique_filename
    
    # Tạo flashcard mới với ID tự động
    new_card = {
        'id': len(user_data.get('flashcards', [])) + 1,
        'question': question,
        'answer': answer,
        'image_url': image_filename  # Lưu tên file
    }
    
    # Cập nhật dữ liệu người dùng
    if 'flashcards' not in user_data:
        user_data['flashcards'] = []
    user_data['flashcards'].append(new_card)
    users[username] = user_data
    save_users(users)
    
    return redirect(url_for('flashcards'))

@app.route('/delete_flashcard/<int:card_id>', methods=['POST'])
def delete_flashcard(card_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    users = load_users()
    user_data = users.get(username, {})
    
    # Tìm flashcard để xóa và xóa file ảnh nếu có
    if 'flashcards' in user_data:
        # Tìm card để xóa
        for card in user_data['flashcards']:
            if card.get('id') == card_id:
                # Xóa file ảnh nếu có
                if card.get('image_url'):
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], card['image_url'])
                    try:
                        if os.path.exists(image_path):
                            os.remove(image_path)
                    except Exception as e:
                        print(f"Lỗi khi xóa file: {e}")
                break
        
        # Xóa flashcard
        user_data['flashcards'] = [
            card for card in user_data['flashcards'] 
            if card.get('id') != card_id
        ]
        users[username] = user_data
        save_users(users)
    
    return redirect(url_for('flashcards'))
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)