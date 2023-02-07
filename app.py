from flask import Flask, redirect, url_for, render_template, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
import string, random
import urllib3
from werkzeug.urls import url_parse  # needed for redirect url control

# need to have QRZ_USER and QRZ_PASSWORD as environment variables
from qrz import QRZ

# Google Sheet
from googleapiclient import discovery
from google.oauth2 import service_account
from time import strftime
from datetime import datetime
from pytz import timezone

# For RadioID requests
import requests

# Disabling "Unverified HTTPS request is being made to host 'xmldata.qrz.com'..." warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

tz = timezone("US/Eastern")
net_control = "<TBD>"  # Net Control station
net_topic = "<TBD>"  # Net topic
announcements = []
questions = []
user_db = []
app = Flask(__name__)
app.secret_key = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
# Disable warning message
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = "False"
db = SQLAlchemy(app)
login_manager = LoginManager(app)
# Google sheet integration
secret_file = "credentials.json"
credentials = service_account.Credentials.from_service_account_file(secret_file)
service = discovery.build("sheets", "v4", credentials=credentials)
# The ID of the spreadsheet to update.
spreadsheet_id = (
    "1KKE_QcvpwWr-Aj3Ch9_lGUiw_HDCUji16cTdsm6BNZY"  # TODO: Update placeholder value.
)
# The A1 notation of a range to search for a logical table of data.
# Values will be appended after the last row of the table.
range_ = "A1"  # TODO: Update placeholder value.
# How the input data should be interpreted.
value_input_option = "USER_ENTERED"  # TODO: Update placeholder value.
# How the input data should be inserted.
insert_data_option = "INSERT_ROWS"  # TODO: Update placeholder value.


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

    def __repr__(self):
        return f"User('{self.username}')"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@login_manager.unauthorized_handler
def unauthorized_handler():
    flash("Unauthorized!", "danger")
    next = url_for(request.endpoint, **request.view_args)
    return redirect(url_for("login", next=next))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        next_page = request.args.get("next")
        if current_user.is_authenticated:
            flash("User is already authenticated", "success")
            if not next_page or url_parse(next_page).netloc != "":
                return redirect(url_for("home"))
            return redirect(next_page)
        # Check for in url variables for username and password
        url_username = request.args.get("username")
        url_password = request.args.get("password")
        if url_username and url_password:
            user = User.query.filter_by(username=url_username).first()
            if user and user.password == url_password:
                login_user(user, remember=True)
                if not next_page or url_parse(next_page).netloc != "":
                    return redirect(url_for("home"))
                return redirect(next_page)
            else:
                flash("Bad password!", "danger")
            return redirect(url_for("home"))
        return render_template("login.html")

    user = User.query.filter_by(username=request.form["usnme"]).first()
    if user and user.password == request.form["pswd"]:
        login_user(user, remember=True)
        next_page = request.args.get("next")
        if not next_page or url_parse(next_page).netloc != "":
            return redirect(url_for("home"))
        return redirect(next_page)
    else:
        flash("Bad password!", "danger")
    return redirect(url_for("home"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out!", "success")
    return redirect(url_for("home"))


@app.route("/")
def home():
    return render_template(
        "index.html",
        net_control=net_control,
        net_topic=net_topic,
        announcements=announcements,
        questions=questions,
        user_db=user_db,
    )


@app.route("/checkin", methods=["POST", "GET"])
@login_required
def checkin():
    global user_db
    if request.method == "POST":
        callsign = request.form["cs"].upper()
        # checking for duplicates (already registered)
        if not callsign:
            flash("Empty callsign!", "danger")
        elif (
            request.form["submit"] == "Lookup on QRZ"
        ):  # Lookup on QRZ button was clicked
            # QRZ lookup
            try:
                result = QRZ().callsign(callsign)
                name = result["fname"] + " " + result["name"]
                location = (
                    result["addr2"] + " " + result["state"] + " " + result["country"]
                )
            except Exception as ex:
                flash("Lookup issue!", "info")
                # return redirect(url_for("home"))
                return render_template("checkin.html", in_callsign=callsign)
            return render_template(
                "checkin.html", in_callsign=callsign, in_name=name, in_location=location
            )
        elif (
            request.form["submit"] == "Lookup on RadioID"
        ):  # Lookup on QRZ button was clicked
            # RadioID lookup
            try:
                url = "https://database.radioid.net"
                radioid_reply = requests.get(
                    url + "/api/dmr/user/?callsign=" + callsign
                )
                radioid_reply_json = radioid_reply.json()
                print(radioid_reply_json)
                name = (
                    radioid_reply_json["results"][0]["fname"]
                    + " "
                    + radioid_reply_json["results"][0]["surname"]
                )
                location = (
                    radioid_reply_json["results"][0]["city"]
                    + " "
                    + radioid_reply_json["results"][0]["state"]
                    + " "
                    + radioid_reply_json["results"][0]["country"]
                )
            except Exception as ex:
                flash("Lookup issue!", "info")
                return render_template("checkin.html", in_callsign=callsign)
            return render_template(
                "checkin.html", in_callsign=callsign, in_name=name, in_location=location
            )
        elif request.form["submit"] == "Submit":  # Submit button was clicked
            if not any(callsign in sublist[0] for sublist in user_db):
                name = request.form["nm"].upper()
                location = request.form["loc"].upper()
                user_db.append((callsign, name, location))
                # Submit to google sheet
                # To Google
                date_string = "{}".format(datetime.now(tz).strftime("%m/%d/%y"))
                time_string = "{}".format(datetime.now(tz).strftime("%H:%M:%S"))
                duplicate = ""
                value_range_body = {
                    "values": [
                        [
                            callsign,
                            name.upper(),
                            location.upper(),
                            "WEB",
                            duplicate,
                            time_string,
                            date_string,
                        ]
                    ]
                }
                google_sheet_request = (
                    service.spreadsheets()
                    .values()
                    .append(
                        spreadsheetId=spreadsheet_id,
                        range=range_,
                        valueInputOption=value_input_option,
                        insertDataOption=insert_data_option,
                        body=value_range_body,
                    )
                )
                response = google_sheet_request.execute()
                flash("Callsign submitted:" + callsign, "success")
            else:
                flash("Duplicate!", "danger")
        return redirect(url_for("home"))
    else:
        return render_template("checkin.html")


@app.route("/ann", methods=["POST", "GET"])
@login_required
def ann():
    global announcements
    if request.method == "POST":
        announcement = request.form["ann"]
        callsign = request.form["cs"].upper()
        if not announcement or not callsign:
            flash("Rejected. Empty fields!", "info")
        else:
            announcements.append((announcement, callsign))
            flash("Announcement submitted!", "success")
        return redirect(url_for("home"))
    else:
        return render_template("ann.html")


@app.route("/ques", methods=["POST", "GET"])
@login_required
def ques():
    global questions
    if request.method == "POST":
        question = request.form["ques"]
        callsign = request.form["cs"].upper()
        if not question or not callsign:
            flash("Rejected. Empty fields!", "info")
        else:
            questions.append((question, callsign))
            flash("Question submitted!", "success")
        return redirect(url_for("home"))
    else:
        return render_template("ques.html")


@app.route("/nettopic", methods=["POST", "GET"])
@login_required
def nettopic():
    global net_topic
    global net_control
    if current_user.username == "admin":
        if request.method == "POST":
            ntctrl = request.form["ntctrl"]
            nttpc = request.form["nttpc"]
            # checking for empty string
            if not nttpc or not ntctrl:
                flash("Both fields should be filled!", "info")
            else:
                if net_topic != nttpc:
                    net_topic = nttpc
                    flash("Net topic is: " + nttpc, "success")
                if net_control != ntctrl:
                    net_control = ntctrl
                    flash("Net control station is: " + ntctrl, "success")
            return redirect(url_for("home"))
        else:
            return render_template(
                "nettopic.html", in_ntctrl=net_control, in_nttpc=net_topic
            )
    else:
        flash("Unauthorized!", "danger")
        return redirect(url_for("home"))


if __name__ == "__main__":
    # admin_password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    # print('Admin password:')
    # print(admin_password)
    admin_password = "superpassword123"
    user_1 = User(username="DMR", password="tg31088")
    user_2 = User(username="admin", password=admin_password)
    with app.app_context():
        db.create_all()
        db.session.add(user_1)
        db.session.add(user_2)
        db.session.commit()
        app.run(debug=True, host="0.0.0.0", port=8080)
