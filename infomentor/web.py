from infomentor import model, db
from flask import Flask, render_template, redirect, url_for, request
from flask_bootstrap import Bootstrap

app = Flask(__name__)
Bootstrap(app)


@app.route("/")
def home():
    return render_template("notfound.html")


@app.route("/addlogin")
def extra():
    return render_template("addlogin.html")


@app.route("/create", methods=["POST"])
def create():
    if request.form["accesscode"] != "fhKjzgV/BXWq4YRxUPO4qYlHWCDf":
        return redirect(url_for("home"))
    session = db.get_db()
    username = request.form["username"]
    existing_user = (
        session.query(model.User).filter(model.User.name == username).one_or_none()
    )
    if existing_user is not None:
        return redirect(url_for("home"))

    password = request.form["password"]
    user = model.User(name=username, password=password)
    if request.form["notify"] == "mail":
        user.notification = [
            model.Notification(
                ntype=model.Notification.Types.EMAIL, info=request.form["info"]
            )
        ]
    else:
        user.notification = [
            model.Notification(
                ntype=model.Notification.Types.PUSHOVER, info=request.form["info"]
            )
        ]
    session.add(user)
    session.commit()
    return "success"


if __name__ == "__main__":
    app.run(debug=True)
