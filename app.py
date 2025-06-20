from flask import Flask, render_template
import os
import pandas as pd

app = Flask(__name__)
BASE_DIR = "amc"

@app.route('/')
def home():
    amcs = os.listdir(BASE_DIR)
    return render_template("index.html", amcs=amcs)

@app.route('/<amc>')
def list_schemes(amc):
    schemes = os.listdir(os.path.join(BASE_DIR, amc))
    return render_template("schemes.html", amc=amc, schemes=schemes)

@app.route('/<amc>/<scheme>')
def show_scheme_data(amc, scheme):
    file_path = os.path.join(BASE_DIR, amc, scheme)
    df = pd.read_csv(file_path)
    return render_template("data.html", table=df.to_html(classes='table table-bordered', index=False))

if __name__ == '__main__':
    app.run(debug=True)
