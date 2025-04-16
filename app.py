from flask import Flask, render_template, request, redirect, session, url_for
from pymongo import MongoClient
import uuid
import os

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret123")  # Better secret key handling

# Database connection
client = MongoClient(os.environ.get("MONGODB_URI", "mongodb://localhost:27017/"))
db = client["MarketMateDB"]
admins_collection = db["admins"]

# Helper functions
def generate_id(prefix):
    """Generate unique ID with given prefix"""
    return prefix + str(uuid.uuid4())[:6]

def is_logged_in():
    """Check if admin is logged in"""
    return "admin_id" in session

# Authentication routes
@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle admin login"""
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        admin = admins_collection.find_one({
            "email": email,
            "password": password  # In production, use password hashing!
        })

        if admin:
            session["admin_id"] = str(admin["admin_ID"])
            return redirect(url_for("show_dashboard"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Handle admin logout"""
    session.pop("admin_id", None)
    return redirect(url_for("login"))

# Main dashboard route
@app.route("/")
def show_dashboard():
    """Display dashboard with statistics"""
    if not is_logged_in():
        return redirect(url_for("login"))

    # Get counts from database
    counts = {
        "admins": db.admins.count_documents({}),
        "devices": db.devices.count_documents({}),
        "images": db.images.count_documents({}),
        "feedbacks": db.feedbacks.count_documents({})
    }

    # Analysis data processing
    analysis = list(db.analysis_results.find())
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

# Admin management routes
@app.route("/admins")
def list_admins():
    """List all admins"""
    if not is_logged_in():
        return redirect(url_for("login"))
    admins = list(db.admins.find())
    return render_template("admins.html", admins=admins)

@app.route("/admins/add", methods=["POST"])
def add_admin():
    """Add new admin"""
    if not is_logged_in():
        return redirect(url_for("login"))

    new_admin = {
        "admin_ID": generate_id("ADM"),
        "email": request.form["email"],
        "password": request.form["password"]  # Remember to hash in production!
    }
    db.admins.insert_one(new_admin)
    return redirect(url_for("list_admins"))

@app.route("/admins/<admin_id>/delete")
def delete_admin(admin_id):
    """Delete an admin"""
    if not is_logged_in():
        return redirect(url_for("login"))
    db.admins.delete_one({"admin_ID": admin_id})
    return redirect(url_for("list_admins"))

@app.route("/admins/<admin_id>/edit", methods=["GET", "POST"])
def edit_admin(admin_id):
    """Edit admin details"""
    if not is_logged_in():
        return redirect(url_for("login"))

    admin = db.admins.find_one({"admin_ID": admin_id})
    
    if request.method == "POST":
        db.admins.update_one(
            {"admin_ID": admin_id},
            {"$set": {
                "email": request.form["email"],
                "password": request.form["password"]
            }}
        )
        return redirect(url_for("list_admins"))
    
    return render_template("edit_admin.html", admin=admin)

# Data management routes
@app.route("/devices")
def list_devices():
    """List all devices"""
    if not is_logged_in():
        return redirect(url_for("login"))
    devices = list(db.devices.find())
    return render_template("devices.html", devices=devices)

@app.route("/images")
def list_images():
    """List all images"""
    if not is_logged_in():
        return redirect(url_for("login"))
    images = list(db.images.find())
    return render_template("images.html", images=images)

@app.route("/analysis")
def show_analysis():
    """Show analysis results"""
    if not is_logged_in():
        return redirect(url_for("login"))
    results = list(db.analysis_results.find())
    return render_template("analysis.html", results=results)

@app.route("/feedbacks")
def list_feedbacks():
    """List all feedbacks"""
    if not is_logged_in():
        return redirect(url_for("login"))
    feedbacks = list(db.feedbacks.find())
    return render_template("feedbacks.html", feedbacks=feedbacks)

# Application entry point
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)