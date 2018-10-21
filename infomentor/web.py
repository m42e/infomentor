from infomentor import models, db
from flask import Flask, render_template
from flask_bootstrap import Bootstrap

app = Flask(__name__)
Bootstrap(app)

@app.route('/')
def home():
	return render_template('notfound.html')

@app.route('/addlogin/')
def extra():
	return render_template('addlogin.html')

if __name__ == '__main__':
	app.run(debug=True)

