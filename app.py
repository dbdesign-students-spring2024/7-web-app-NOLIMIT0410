#!/usr/bin/env python3
import os
import sys
import subprocess
import datetime
import pymongo
import sentry_sdk

from flask import Flask, render_template, request, redirect, url_for, make_response
from sentry_sdk.integrations.flask import (
    FlaskIntegration,
)  # delete this if not using sentry.io


from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId
from flask_login import LoginManager,login_user, logout_user, login_required,current_user
from dotenv import load_dotenv
from model import User

# load credentials and configuration options from .env file
# if you do not yet have a file named .env, make one based on the template in env.example
load_dotenv(override=True)  # take environment variables from .env.

# initialize Sentry for help debugging... this requires an account on sentrio.io
# you will need to set the SENTRY_DSN environment variable to the value provided by Sentry
# delete this if not using sentry.io
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    # enable_tracing=True,
    # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100% of sampled transactions.
    # We recommend adjusting this value in production.
    # profiles_sample_rate=1.0,
    integrations=[FlaskIntegration()],
    send_default_pii=True,
)

# instantiate the app using sentry for debugging
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# # turn on debugging if in development mode
# app.debug = True if os.getenv("FLASK_ENV", "development") == "development" else False

# try to connect to the database, and quit if it doesn't work
try:
    cxn = pymongo.MongoClient(os.getenv("MONGO_URI"))
    db = cxn[os.getenv("MONGO_DBNAME")]  # store a reference to the selected database

    # verify the connection works by pinging the database
    cxn.admin.command("ping")  # The ping command is cheap and does not require auth.
    print(" * Connected to MongoDB!")  # if we get here, the connection worked!
except ConnectionFailure as e:
    # catch any database errors
    # the ping command failed, so the connection is not available.
    print(" * MongoDB connection error:", e)  # debug
    sentry_sdk.capture_exception(e)  # send the error to sentry.io. delete if not using
    sys.exit(1)  # this is a catastrophic error, so no reason to continue to live

# initial login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# set up the routes
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


# login module
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.validate_login(username, password)
        if user:
            login_user(user)
            return redirect(url_for('read'))
        else:
            return 'Invalid username or password'
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']  
        user= User.create(username,password)
        login_user(user)
        return redirect(url_for('home'))
    return render_template('signup.html')

# other function routes
@app.route("/")
def home():
    """
    Route for the home page.
    Simply returns to the browser the content of the index.html file located in the templates folder.
    """
    return render_template("index.html")


@app.route("/read")
@login_required
def read():
    """
    Route for GET requests to the read page.
    Displays some information for the user with links to other pages.
    """
    docs = db.exampleapp.find({"user_id": current_user.id}).sort("created_at", -1)
    return render_template("read.html", docs=docs) 


@app.route("/create")
def create():
    """
    Route for GET requests to the create page.
    Displays a form users can fill out to create a new document.
    """
    return render_template("create.html")


@app.route("/create", methods=["POST"])
@login_required
def create_post():
    """
    Route for POST requests to the create page.
    Accepts the form submission data for a new document and saves the document to the database.
    """
    date = request.form["date"]
    calory = request.form["calory"]
    exercises = request.form.getlist("exercise[]")
    reps_list = request.form.getlist("reps[]")
    time_hours_list = request.form.getlist("time_hours[]")
    time_minutes_list = request.form.getlist("time_minutes[]")
    weights_list = request.form.getlist("weights[]")

    # Create a list of exercise details
    exercise_details = []
    for i in range(len(exercises)):
        exercise_details.append({
            "exercise": exercises[i],
            "reps": reps_list[i],
            "time_hours": time_hours_list[i],
            "time_minutes":time_minutes_list[i],
            "weights": weights_list[i]
        })

    # Create a new document with the data the user entered
    doc = {
        "date": date,
        "calory": calory,
        "exercises": exercise_details,
        "user_id":current_user.id,
        "created_at": datetime.datetime.utcnow()
    }
    db.exampleapp.insert_one(doc)  # insert the new document

    return redirect(url_for("read"))  # Redirect to the read route after posting


@app.route("/edit/<mongoid>")
def edit(mongoid):
    """
    Route for GET requests to the edit page.
    Displays a form users can fill out to edit an existing record.

    Parameters:
    mongoid (str): The MongoDB ObjectId of the record to be edited.
    """
    doc = db.exampleapp.find_one({"_id": ObjectId(mongoid)})
    return render_template(
        "edit.html", mongoid=mongoid, doc=doc
    )  # render the edit template


@app.route("/edit/<mongoid>", methods=["POST"])
@login_required
def edit_post(mongoid):
    """
    Route for POST requests to the edit page.
    Accepts the form submission data for the specified document and updates the document in the database.

    Parameters:
    mongoid (str): The MongoDB ObjectId of the record to be edited.
    """
    doc = db.exampleapp.find_one({"_id": ObjectId(mongoid), "user_id": current_user.id})
    if not doc:
        return "Unauthorized", 403

    # Update the document with new data from the form
    db.exampleapp.update_one(
        {"_id": ObjectId(mongoid)},
        {"$set": {
            "date": request.form["date"],
            "calory": request.form["calory"],
            "exercises": [
                {
                    "exercise": ex,
                    "reps": reps,
                    "time_hours": hours,
                    "time_minutes": minutes,
                    "weights": weights
                } for ex, reps, hours, minutes, weights in zip(
                    request.form.getlist("exercise[]"),
                    request.form.getlist("reps[]"),
                    request.form.getlist("time_hours[]"),
                    request.form.getlist("time_minutes[]"),
                    request.form.getlist("weights[]")
                )
            ],
            "updated_at": datetime.datetime.utcnow()
        }}
    )
    return redirect(url_for("read"))


@app.route("/delete/<mongoid>")
@login_required
def delete(mongoid):
    """
    Route for GET requests to the delete page.
    Deletes the specified record from the database, and then redirects the browser to the read page.

    Parameters:
    mongoid (str): The MongoDB ObjectId of the record to be deleted.
    """
    # Only delete the record if it belongs to the current user
    result = db.exampleapp.delete_one({"_id": ObjectId(mongoid), "user_id": current_user.id})
    if result.deleted_count == 0:
        return "Unauthorized or No record found", 403  # Or handle as preferred

    return redirect(url_for("read"))


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    GitHub can be configured such that each time a push is made to a repository, GitHub will make a request to a particular web URL... this is called a webhook.
    This function is set up such that if the /webhook route is requested, Python will execute a git pull command from the command line to update this app's codebase.
    You will need to configure your own repository to have a webhook that requests this route in GitHub's settings.
    Note that this webhook does do any verification that the request is coming from GitHub... this should be added in a production environment.
    """
    # run a git pull command
    process = subprocess.Popen(["git", "pull"], stdout=subprocess.PIPE)
    pull_output = process.communicate()[0]
    # pull_output = str(pull_output).strip() # remove whitespace
    process = subprocess.Popen(["chmod", "a+x", "flask.cgi"], stdout=subprocess.PIPE)
    chmod_output = process.communicate()[0]
    # send a success response
    response = make_response(f"output: {pull_output}", 200)
    response.mimetype = "text/plain"
    return response


@app.errorhandler(Exception)
def handle_error(e):
    """
    Output any errors - good for debugging.
    """
    return render_template("error.html", error=e)  # render the edit template


# run the app
if __name__ == "__main__":
    # logging.basicConfig(filename="./flask_error.log", level=logging.DEBUG)
    app.run(load_dotenv=True)
