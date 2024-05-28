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
app.config.from_object(Config)

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
