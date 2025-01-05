import os
from flask import Flask, render_template, request, redirect, session, flash, jsonify
from pymongo import MongoClient
from flask_mail import Mail, Message
from datetime import datetime
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import random
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

try:
    mail = Mail(app)
except Exception as e:
    print(f"Error initializing mail: {e}")

# MongoDB setup
client = MongoClient(os.getenv('MONGO_URI'))
db = client['nav_bharath_school']
forms_collection = db['admission_forms']
admin_collection = db['admin_users']
deleted_forms_collection = db['deleted_forms']

# Default Admin Credentials (create on first run)
if not admin_collection.find_one({"username": "admin"}):
    admin_collection.insert_one({
        "username": "admin",
        "password": generate_password_hash("password123")
    })

# Decorator to restrict access to admin-only pages
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# Home Route (index.html)
@app.route("/")
def home():
    return render_template("index.html")

# Admin Login Route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        admin = admin_collection.find_one({"username": username})

        if admin and check_password_hash(admin["password"], password):
            session["admin"] = username
            return redirect("/dashboard")
        else:
            flash("Invalid username or password!")
    return render_template("login.html")

# Admin Logout Route
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/login")

# Dashboard Route for Admin (listing admission forms)
@app.route("/dashboard")
@admin_required
def dashboard():
    forms = forms_collection.find()
    return render_template("dashboard.html", forms=forms)

# Add this function to validate email configuration
def validate_email_config():
    required_configs = [
        'MAIL_SERVER',
        'MAIL_PORT',
        'MAIL_USERNAME',
        'MAIL_PASSWORD',
        'ADMIN_EMAIL'
    ]
    
    missing = []
    for config in required_configs:
        if not os.getenv(config):
            missing.append(config)
    
    if missing:
        print(f"Warning: Missing email configurations: {', '.join(missing)}")
        return False
    return True

# Route to handle admission form submission
@app.route('/admission_form', methods=['POST'])
def handle_admission():
    try:
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        grade = request.form.get('class')
        pincode = request.form.get('pincode')
        reference = request.form.get('reference')

        # Check if email or phone already exists
        existing_submission = forms_collection.find_one({
            "$or": [
                {"email": email},
                {"phone": phone}
            ]
        })

        if existing_submission:
            return jsonify({
                'error': 'You have already submitted an admission form. Please contact the school office for any queries.'
            }), 400

        # Generate unique 4-digit student ID
        while True:
            student_id = str(random.randint(1000, 9999))
            if not forms_collection.find_one({"student_id": student_id}):
                break

        # Create data dictionary
        data = {
            "name": name,
            "email": email,
            "phone": phone,
            "class": grade,
            "pincode": pincode,
            "reference": reference,
            "student_id": student_id,
            "processed": False,
            "submission_date": datetime.now()
        }
        
        # Save to database first
        forms_collection.insert_one(data)

        # Try to send emails if configuration is valid
        if validate_email_config():
            try:
                # Create and send admin email
                email_body = f"""
                New Admission Enquiry:
                
                Student ID: {student_id}
                Name: {name}
                Email: {email}
                Phone: {phone}
                Grade: {grade}
                Pincode: {pincode}
                Reference: {reference}
                
                Submitted on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """

                msg = Message(
                    subject='New Admission Enquiry',
                    recipients=[os.getenv('ADMIN_EMAIL')],
                    body=email_body
                )
                mail.send(msg)

                # Send confirmation email to parent
                confirmation_msg = Message(
                    subject='Admission Enquiry Confirmation - Nav Bharath Vidyalaya',
                    recipients=[email],
                    body=f"""
                    Dear {name},

                    Thank you for your interest in Nav Bharath Vidyalaya. We have received your admission enquiry.
                    
                    Your Enquiry ID is: {student_id}
                    
                    Our admissions team will contact you shortly.
                    
                    Best regards,
                    Nav Bharath Vidyalaya
                    """
                )
                mail.send(confirmation_msg)
            except Exception as e:
                print(f"Email sending failed: {e}")
                # Continue execution even if email fails
                
        return jsonify({
            'message': 'Admission enquiry submitted successfully!',
            'student_id': student_id
        })

    except Exception as e:
        print(f"Error in handle_admission: {e}")
        return jsonify({'error': str(e)}), 500

# Route to update status of admission forms (processed or not)
@app.route("/update_status", methods=["POST"])
@admin_required
def update_status():
    data = request.json
    form_id = data.get("id")
    processed = data.get("processed", False)
    forms_collection.update_one({"_id": ObjectId(form_id)}, {"$set": {"processed": processed}})
    return "", 200

# Route to delete selected forms from the dashboard
@app.route("/delete_forms", methods=["POST"])
@admin_required
def delete_forms():
    delete_ids = request.form.getlist("delete_ids")
    for form_id in delete_ids:
        form = forms_collection.find_one({"_id": ObjectId(form_id)})
        if form:
            deleted_forms_collection.insert_one(form)
            forms_collection.delete_one({"_id": ObjectId(form_id)})
    return redirect("/dashboard")

# Route to show deleted forms on recovery page
@app.route("/recovery")
@admin_required
def recovery():
    deleted_forms = deleted_forms_collection.find()
    return render_template("recovery.html", deleted_forms=deleted_forms)

# Route to recover selected forms back to the admission forms
@app.route("/recover_forms", methods=["POST"])
@admin_required
def recover_forms():
    recover_ids = request.form.getlist("recover_ids")
    for form_id in recover_ids:
        form = deleted_forms_collection.find_one({"_id": ObjectId(form_id)})
        if form:
            forms_collection.insert_one({**form, "processed": False})
            deleted_forms_collection.delete_one({"_id": ObjectId(form_id)})
    return redirect("/recovery")

# Route to delete all forms from the recovery page (permanent deletion)
@app.route("/delete_all_forms", methods=["POST"])
@admin_required
def delete_all_forms():
    # Delete all documents in the 'deleted_forms' collection
    deleted_forms_collection.delete_many({})
    return redirect("/recovery")



# Main route to run the app
if __name__ == "__main__":
    app.run(debug=True)
