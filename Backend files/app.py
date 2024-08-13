import os
import mysql.connector
from flask import Flask, request, g, redirect, url_for, render_template, flash, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from text_detector import TextDetector
from datetime import datetime

# Database configuration
DATABASE_CONFIG = {
    'user': 'textuser',
    'password': 'password',
    'host': '127.0.0.1',
    'database': 'text_detection_db',
    'raise_on_warnings': True
}

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'super secret key'

# Update the path to your Google Cloud Translation API key JSON file
text_detector = TextDetector(ocr_path='D:/29-07-2024_all of desktop content/python_project/tesseract.exe', 
                             translation_api_key='C:/Users/Welcome/Downloads/regal-muse-430609-v0-20d04d657aef.json')


def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(**DATABASE_CONFIG)
        g.cursor = g.db.cursor(dictionary=True)
    return g.db, g.cursor

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.teardown_appcontext
def teardown_db(exception):
    close_db(exception)

# def init_db():
#     db, cursor = get_db()
#     with app.open_resource('schema.sql', mode='r') as f:
#         cursor.execute(f.read(), multi=True)
#     db.commit()

def init_db():
    with app.app_context():
        db, cursor = get_db()
        # If you don't need to execute schema.sql, comment out or remove the lines below
        # with app.open_resource('schema.sql', mode='r') as f:
        #     cursor.execute(f.read(), multi=True)
        db.commit()


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        
        try:
            db, cursor = get_db()
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
            db.commit()
            flash('User registered successfully', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Username already taken', 'danger')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db, cursor = get_db()
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
            # return render_template('login.html')  # Return here to avoid multiple flashes
    
    return render_template('login.html')



@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('index.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    extracted_text = None
    detected_lang = None
    operation_name = "Extracted Text"

    if request.method == 'POST':
        file = request.files['file']
        operation = request.form['operation']
        target_language = request.form['translate_to']
        if file and allowed_file(file.filename):
            filename = file.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Normalize file path to use forward slashes before saving to database
            normalized_file_path = file_path.replace('\\', '/')
            
            extracted_text, detected_lang = text_detector.process_image(file_path, operation=operation, target_language=target_language)
            
            if operation == 'translate':
                operation_name = "Translated Text"
            elif operation == 'summarize':
                operation_name = "Summarized Text"
            else:
                operation_name = "Extracted Text"

            db, cursor = get_db()
            cursor.execute("INSERT INTO images (user_id, image_path, extracted_text) VALUES (%s, %s, %s)",
                           (session['user_id'], normalized_file_path, extracted_text))
            db.commit()

            flash(f'File uploaded and text extracted successfully. Detected language: {detected_lang}', 'success')
    
    return render_template('upload.html', extracted_text=extracted_text, detected_lang=detected_lang, operation_name=operation_name)

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db, cursor = get_db()
    cursor.execute('SELECT * FROM images WHERE user_id = %s', (session['user_id'],))
    images = cursor.fetchall()
    
    #print(images)  # Debug statement to see the structure of images in the console
    
    return render_template('history.html', images=images)



@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/download/<int:image_id>')
def download_text(image_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db, cursor = get_db()
    cursor.execute('SELECT * FROM images WHERE id = %s AND user_id = %s', (image_id, session['user_id']))
    image = cursor.fetchone()
    if image:
        text_filename = f"text_{image_id}.txt"
        with open(os.path.join(app.config['UPLOAD_FOLDER'], text_filename), 'w') as f:
            f.write(image['extracted_text'])
        
        return send_from_directory(app.config['UPLOAD_FOLDER'], text_filename, as_attachment=True)
    else:
        flash('No such text found', 'danger')
        return redirect(url_for('history'))

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    init_db()
    app.run(debug=True)
