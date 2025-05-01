from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_sitemapper import Sitemapper
import bcrypt
import requests
import datetime
import bard, os
from dotenv import load_dotenv

# Load the environment variables
load_dotenv()
api_key = os.environ.get("WEATHER_API_KEY")
secret_key = os.environ.get("SECRET_KEY")

# Initialize the app (Fix: Use __name__ instead of _name_)
app = Flask(__name__)
sitemapper = Sitemapper(app=app)  # Create and initialize the sitemapper
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
app.secret_key = secret_key

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    # Fix: Use __init__ instead of _init_
    def __init__(self, name, email, password):
        self.name = name
        self.email = email
        self.password = bcrypt.hashpw(password.encode('utf8'), bcrypt.gensalt()).decode('utf8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf8'), self.password.encode('utf8'))

with app.app_context():
    db.create_all()

# Weather Data 
def get_weather_data(api_key: str, location: str, start_date: str, end_date: str) -> dict:
    """
    Retrieves weather data from Visual Crossing Weather API for a given location and date range.
    """
    base_url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{location}/{start_date}/{end_date}?unitGroup=metric&include=days&key={api_key}&contentType=json"

    try:
        response = requests.get(base_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print("Error:", str(e))  # Fix: Use str(e) for exception string formatting

@sitemapper.include()  # Include the route in the sitemap
@app.route('/', methods=["GET", "POST"])
def index():
    """
    Renders the index.html template.
    """
    if request.method == "POST":
        # Avoid global variables (Fix): Get data directly from the form
        source = request.form.get("source")
        destination = request.form.get("destination")
        start_date = request.form.get("date")
        end_date = request.form.get("return")

        # Calculating the number of days
        no_of_day = (datetime.datetime.strptime(end_date, "%Y-%m-%d") - datetime.datetime.strptime(start_date, "%Y-%m-%d")).days

        if no_of_day < 0:
            flash("Return date should be greater than the Travel date (Start date).", "danger")
            return redirect(url_for("index"))
        else:
            try:
                weather_data = get_weather_data(api_key, destination, start_date, end_date)
            except requests.exceptions.RequestException as e:
                flash(f"Error in retrieving weather data: {str(e)}", "danger")  # Fix: Correct error formatting
                return redirect(url_for("index"))

        try:
            plan = bard.generate_itinerary(source, destination, start_date, end_date, no_of_day)
        except Exception as e:
            flash(f"Error in generating the plan. Please try again later: {str(e)}", "danger")
            return redirect(url_for("index"))

        # Render the weather information in the template
        return render_template("dashboard.html", weather_data=weather_data, plan=plan)

    return render_template('index.html')

@sitemapper.include()  # Include the route in the sitemap
@app.route("/about")
def about():
    return render_template("about.html")

@sitemapper.include()  # Include the route in the sitemap
@app.route("/contact")
def contact():
    user_email = session.get('user_email', "Enter your email")
    user_name = session.get('user_name', "Enter your name")
    return render_template("contact.html", user_email=user_email, user_name=user_name, message="")

@sitemapper.include()  # Include the route in the sitemap
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["user_name"] = user.name
            session["user_email"] = user.email
            flash("Login successful.", "success")
            return redirect(url_for("index"))
        else:
            flash("Wrong email or password. Please try again or register now.", "danger")
            return redirect(url_for("login"))
    return render_template("login.html")

@sitemapper.include()  # Include the route in the sitemap
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

@sitemapper.include()  # Include the route in the sitemap
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        password2 = request.form.get("password2")

        if password == password2:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash("User already exists. Please log in.", "danger")
                return redirect("/login")
            else:
                user = User(name=name, email=email, password=password)
                db.session.add(user)
                db.session.commit()
                return redirect("/login")
        else:
            flash("Passwords do not match.", "danger")
            return redirect("/register")
    return render_template("register.html")

# Robots.txt
@app.route('/robots.txt')
def robots():
    return render_template('robots.txt')

# Sitemap
@app.route("/sitemap.xml")
def r_sitemap():
    return sitemapper.generate()

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Inject current time for templates
@app.context_processor
def inject_now():
    return {'now': datetime.datetime.now()}
