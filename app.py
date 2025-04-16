from flask import Flask, render_template, request, redirect, session, url_for
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

# Connect to MongoDB Atlas
try:
    client = MongoClient(
        os.environ.get("MONGODB_URI", "mongodb://localhost:27017/"),
        connectTimeoutMS=30000,
        socketTimeoutMS=None
    )
    db = client["MarketMateDB"]
    admins_collection = db["admins"]
    client.admin.command('ping')  # Test connection
except Exception as e:
    print(f"Database connection error: {e}")
    raise

# Helper functions
def generate_id(prefix):
    return prefix + str(uuid.uuid4())[:8]

def is_logged_in():
    return "admin_id" in session

def hash_password(password):
    return generate_password_hash(password, method='pbkdf2:sha256')

def verify_password(hashed_password, password):
    return check_password_hash(hashed_password, password)

# Authentication routes
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        admin = admins_collection.find_one({"email": email})
        if admin and verify_password(admin["password"], password):
            session.clear()
            session["admin_id"] = str(admin["admin_ID"])
            session.permanent = True
            return redirect(url_for("show_dashboard"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Dashboard
@app.route("/")
def show_dashboard():
    if not is_logged_in():
        return redirect(url_for("login"))
    try:
        counts = {
            "admins": admins_collection.count_documents({}),
            "devices": db.devices.count_documents({}),
            "images": db.images.count_documents({}),
            "feedbacks": db.feedbacks.count_documents({})
        }

        analysis = list(db.analysis_results.find({}, {"quality_score": 1, "error_flag": 1}))
        scores = [res.get("quality_score", 0) for res in analysis if res.get("quality_score") is not None]
        avg_score = round(sum(scores)/len(scores), 2) if scores else 0

        quality_counts = {
            "excellent": sum(1 for res in analysis if res.get("quality_score", 0) > 0.5),
            "low": sum(1 for res in analysis if res.get("quality_score", 0) <= 0.5 and not res.get("error_flag", False)),
            "error": sum(1 for res in analysis if res.get("error_flag", False))
        }

        return render_template("dashboard.html",
            counts=counts,
            avg_quality_score=avg_score,
            quality_counts=quality_counts
        )
    except Exception as e:
        print(f"Dashboard error: {e}")
        return render_template("error.html", message="Failed to load dashboard data"), 500

# Admin management
@app.route("/admins")
def list_admins():
    if not is_logged_in():
        return redirect(url_for("login"))
    try:
        admins = list(admins_collection.find({}, {"password": 0}))
        return render_template("admins.html", admins=admins)
    except Exception as e:
        print(f"Admin list error: {e}")
        return redirect(url_for("show_dashboard"))

@app.route("/admins/add", methods=["POST"])
def add_admin():
    if not is_logged_in():
        return redirect(url_for("login"))
    try:
        new_admin = {
            "admin_ID": generate_id("ADM"),
            "email": request.form.get("email", "").strip(),
            "password": hash_password(request.form.get("password", ""))
        }
        admins_collection.insert_one(new_admin)
        return redirect(url_for("list_admins"))
    except Exception as e:
        print(f"Add admin error: {e}")
        return redirect(url_for("list_admins"))

@app.route("/admins/<admin_id>/delete")
def delete_admin(admin_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    if str(session.get("admin_id")) == admin_id:
        return redirect(url_for("list_admins", error="Cannot delete current admin"))
    try:
        admins_collection.delete_one({"admin_ID": admin_id})
        return redirect(url_for("list_admins"))
    except Exception as e:
        print(f"Delete admin error: {e}")
        return redirect(url_for("list_admins"))

@app.route("/admins/<admin_id>/edit", methods=["GET", "POST"])
def edit_admin(admin_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    try:
        admin = admins_collection.find_one({"admin_ID": admin_id})
        if not admin:
            return redirect(url_for("list_admins"))
        if request.method == "POST":
            update_data = {"email": request.form.get("email", "").strip()}
            if request.form.get("password"):
                update_data["password"] = hash_password(request.form.get("password"))
            admins_collection.update_one({"admin_ID": admin_id}, {"$set": update_data})
            return redirect(url_for("list_admins"))
        return render_template("edit_admin.html", admin=admin)
    except Exception as e:
        print(f"Edit admin error: {e}")
        return redirect(url_for("list_admins"))

# Devices route with pagination
@app.route("/devices")
def list_devices():
    if not is_logged_in():
        return redirect(url_for("login"))
    try:
        page = int(request.args.get('page', 1))
        per_page = 10
        devices = list(db.devices.find().skip((page-1)*per_page).limit(per_page))
        return render_template("devices.html", devices=devices, page=page)
    except Exception as e:
        print(f"Devices list error: {e}")
        return render_template("error.html", message="Failed to load devices"), 500

# Entry point
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
