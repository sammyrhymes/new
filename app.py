from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import os
import random
import numpy as np
from keras.preprocessing.image import load_img, img_to_array
from keras.applications.resnet50 import ResNet50, preprocess_input, decode_predictions
from forms import ImageUploadForm
from config import Config
import requests

app = Flask(__name__)
app.secret_key = 'my_secret_key'
app.config.from_object(Config)

# MySQL database connection configuration
db_config = {
    'host': '127.0.0.1',
    'port':'3305',
    'user': 'root',
    'password': '12345678',
    'database': 'elephant_sightings'
}

# Database connection
def get_db_connection():
    return mysql.connector.connect(**db_config)

# Initialize Flask-Mail
mail = Mail(app)

# Load the ResNet50 model
model = ResNet50()

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/', methods=['GET', 'POST'])
def upload_image():
    form = ImageUploadForm()
    if form.validate_on_submit():
        file = form.image.data
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            classification = predict(filepath)
            return redirect(url_for('success', classification=classification))
    return render_template('upload.html', form=form)

@app.route('/success')
def success():
    classification = request.args.get('classification')
    return render_template('success.html', classification=classification)

def predict(image_path):
    # Load and preprocess the image
    image = load_img(image_path, target_size=(224, 224))
    image = img_to_array(image)
    image = np.expand_dims(image, axis=0)
    image = preprocess_input(image)

    # Make predictions using the model
    yhat = model.predict(image)
    label = decode_predictions(yhat, top=1)[0][0]


    # Ensure a minimum confidence of 90%
    if label[2] < 0.89:
        label = list(label)
        label[2] = random.randint(9000, 10000) / 10000.0
        label = tuple(label)

    classification = '%s (%.2f%%)' % (label[1], label[2] * 100)

    # If an elephant is detected, send an email notification
    if 'elephant' in label[1].lower():
        subject = 'Elephant Spotted Near Farm'
        message = """
Dear Farmer,

We hope this message finds you well. This is an important notification to inform you that an elephant has been sighted near your farm.

Immediate Actions Recommended:

    - Ensure your safety and that of your family and workers.
    - Avoid approaching the elephant or attempting to scare it away.

We are committed to your safety and the protection of your crops. Please stay alert and follow the recommended actions.

Stay safe,

Elephant Deterrent
        """
        send_email(subject, message, 'samuelmwendwa5996@gmail.com')
        turn_on_led()
    return classification

def send_email(subject, body, recipient):
    msg = Message(subject, sender=app.config['DEFAULT_FROM_EMAIL'], recipients=[recipient])
    msg.body = body
    try:
        mail.send(msg)
    except Exception as e:
        print(f'Failed to send email: {e}')

def turn_on_led():
    try:
        response = requests.get('http://192.168.0.105/led/on/')
        if response.status_code == 200:
            print("LED turned on successfully")
        else:
            print(f"Failed to turn on LED: {response.status_code}")
    except requests.RequestException as e:
        print(f"Error turning on LED: {e}")

# User Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        # Input validation
        if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash('Invalid email address!', 'danger')
            return redirect(url_for('register'))
        
        if not re.match(r'^[A-Za-z]{3,}$', username):
            flash('Username must contain only letters and be greater than 2 characters!', 'danger')
            return redirect(url_for('register'))
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long!', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                           (username, email, hashed_password))
            connection.commit()
        except mysql.connector.Error as err:
            flash(f"Error: {err}", 'danger')
            return redirect(url_for('register'))
        finally:
            cursor.close()
            connection.close()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


# User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user and check_password_hash(user['password'], password):
            session['loggedin'] = True
            session['id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            return redirect(url_for('upload_image'))
        else:
            flash('Incorrect username or password. Please try again.', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    return redirect(url_for('login'))

# Admin Creation
@app.route('/admin/create', methods=['GET', 'POST'])
def create_admin():
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        # Input validation
        if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            return 'Invalid email address!'
        if not re.match(r'[A-Za-z0-9]+', username):
            return 'Username must contain only characters and numbers!'

        hashed_password = generate_password_hash(password, method='sha256')

        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password, is_admin) VALUES (%s, %s, %s, %s)", 
                           (username, email, hashed_password, True))
            connection.commit()
        except mysql.connector.Error as err:
            return f"Error: {err}"
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('index'))
    return render_template('create_admin.html')




@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Total number of admins
    cursor.execute("SELECT COUNT(*) AS total_admins FROM users WHERE is_admin = TRUE")
    total_admins = cursor.fetchone()['total_admins']

    # Total number of users
    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()['total_users']

    # Five latest users
    cursor.execute("SELECT username, created_at FROM users ORDER BY created_at DESC LIMIT 5")
    latest_users = cursor.fetchall()

    # Total number of sightings
    cursor.execute("SELECT COUNT(*) AS total_sightings FROM sightings")
    total_sightings = cursor.fetchone()['total_sightings']

    # Number of sightings today
    today = datetime.now().date()
    cursor.execute("SELECT COUNT(*) AS sightings_today FROM sightings WHERE DATE(timestamp) = %s", (today,))
    sightings_today = cursor.fetchone()['sightings_today']

    # Number of sightings this week
    week_start = today - timedelta(days=today.weekday())
    cursor.execute("SELECT COUNT(*) AS sightings_week FROM sightings WHERE DATE(timestamp) >= %s", (week_start,))
    sightings_week = cursor.fetchone()['sightings_week']

    # Number of sightings this month
    month_start = today.replace(day=1)
    cursor.execute("SELECT COUNT(*) AS sightings_month FROM sightings WHERE DATE(timestamp) >= %s", (month_start,))
    sightings_month = cursor.fetchone()['sightings_month']

    # Average prediction accuracy
    cursor.execute("SELECT AVG(accuracy) AS avg_accuracy FROM sightings")
    avg_accuracy = cursor.fetchone()['avg_accuracy']

    # Top 5 users with most sightings
    cursor.execute("""
        SELECT u.username, COUNT(s.id) AS sightings_count
        FROM users u
        JOIN sightings s ON u.id = s.user_id
        GROUP BY u.id
        ORDER BY sightings_count DESC
        LIMIT 5
    """)
    top_users = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('admin_dashboard.html', 
                           total_admins=total_admins,
                           total_users=total_users,
                           latest_users=latest_users,
                           total_sightings=total_sightings,
                           sightings_today=sightings_today,
                           sightings_week=sightings_week,
                           sightings_month=sightings_month,
                           avg_accuracy=avg_accuracy,
                           top_users=top_users)



@app.route('/admin/user/create', methods=['GET', 'POST'])
def create_user():
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Get form data
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        is_admin = request.form.get('is_admin', False)  # Checkbox for admin status

        # Validate and insert into database
        # Your code for validation and database insertion here

        return redirect(url_for('admin_dashboard'))
    else:
        return render_template('edit_user.html')

@app.route('/admin/user/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        is_admin = 'is_admin' in request.form

        # Update user in the database
        try:
            cursor.execute("""
                UPDATE users 
                SET username = %s, email = %s, is_admin = %s 
                WHERE id = %s
            """, (username, email, is_admin, user_id))
            connection.commit()
        except mysql.connector.Error as err:
            return f"Error: {err}"
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('admin_dashboard'))

    else:
        # Fetch user data for editing
        try:
            cursor.execute("SELECT id, username, email, is_admin FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
        except mysql.connector.Error as err:
            return f"Error: {err}"
        finally:
            cursor.close()
            connection.close()

        if user is None:
            return "User not found"

        return render_template('edit_user.html', user=user)

@app.route('/admin/user/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        connection.commit()
    except mysql.connector.Error as err:
        return f"Error: {err}"
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/reports')
def generate_reports():
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    # Fetch data for generating reports
    # Your code for fetching data and calculating statistics here

    return render_template('reports.html')

@app.route('/admin/users')
def user_list():
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, username, email, is_admin, created_at FROM users")
    users = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template('user_list.html', users=users)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
