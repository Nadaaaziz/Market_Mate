from flask import Flask, render_template, request, redirect, session, url_for
from pymongo import MongoClient
import uuid
import os

app = Flask(__name__)
app.secret_key = "secret123"

# MongoDB Local - لو هتشغلي أونلاين ممكن تحتاجي Mongo Atlas
client = MongoClient("mongodb://localhost:27017/")
db = client["MarketMateDB"]
admins_collection = db["admins"]

def generate_id(prefix):
    return prefix + str(uuid.uuid4())[:6]

def is_logged_in():
    return "admin_id" in session

# --- Dashboard ---
@app.route("/")
def dashboard():
    if "admin_id" not in session:
        return redirect(url_for("login"))

    total_admins = db.admins.count_documents({})
    total_devices = db.devices.count_documents({})
    total_images = db.images.count_documents({})
    total_feedbacks = db.feedbacks.count_documents({})

    analysis = list(db.analysis_results.find())
    scores = [res.get("quality_score", 0) for res in analysis if res.get("quality_score") is not None]
    avg_score = round(sum(scores)/len(scores), 2) if scores else 0

    excellent = sum(1 for res in analysis if res.get("quality_score", 0) > 0.5)
    low = sum(1 for res in analysis if res.get("quality_score", 0) <= 0.5 and not res.get("error_flag", False))
    error = sum(1 for res in analysis if res.get("error_flag", False))

    return render_template("dashboard.html",
        total_admins=total_admins,
        total_devices=total_devices,
        total_images=total_images,
        total_feedbacks=total_feedbacks,
        avg_quality_score=avg_score,
        excellent_count=excellent,
        low_count=low,
        error_count=error
    )

# --- Admins ---
@app.route("/admins")
def admins():
    if not is_logged_in():
        return redirect(url_for("login"))
    admins = list(db.admins.find())
    return render_template("admins.html", admins=admins)

@app.route("/add_admin", methods=["POST"])
def add_admin():
    if not is_logged_in():
        return redirect(url_for("login"))
    new_admin = {
        "admin_ID": generate_id("ADM"),
        "email": request.form["email"],
        "password": request.form["password"]
    }
    db.admins.insert_one(new_admin)
    return redirect(url_for("admins"))

@app.route("/delete_admin/<admin_id>")
def delete_admin(admin_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    db.admins.delete_one({"admin_ID": admin_id})
    return redirect(url_for("admins"))

@app.route("/edit_admin/<admin_id>", methods=["GET", "POST"])
def edit_admin(admin_id):
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
        return redirect(url_for("admins"))
    return render_template("edit_admin.html", admin=admin)

# --- Devices ---
@app.route("/devices")
def devices():
    if not is_logged_in():
        return redirect(url_for("login"))
    devices = list(db.devices.find())
    return render_template("devices.html", devices=devices)

# --- Images ---
@app.route("/images")
def images():
    if not is_logged_in():
        return redirect(url_for("login"))
    images = list(db.images.find())
    return render_template("images.html", images=images)

# --- Analysis ---
@app.route("/analysis")
def analysis():
    if not is_logged_in():
        return redirect(url_for("login"))
    results = list(db.analysis_results.find())
    return render_template("analysis.html", results=results)

# --- Feedbacks ---
@app.route("/feedbacks")
def feedbacks():
    if not is_logged_in():
        return redirect(url_for("login"))
    feedbacks = list(db.feedbacks.find())
    return render_template("feedbacks.html", feedbacks=feedbacks)

# --- Login ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        admin = admins_collection.find_one({
            "email": email,
            "password": password
        })

        if admin:
            session["admin_id"] = str(admin["admin_ID"])
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

# --- Logout ---
@app.route("/logout")
def logout():
    session.pop("admin_id", None)
    return redirect(url_for("login"))

# --- تشغيل السيرفر ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # ضروري لـ Railway
    app.run(debug=True, host="0.0.0.0", port=port)
