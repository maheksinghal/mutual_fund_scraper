from flask import Flask, render_template, request, jsonify
import os
import pandas as pd

app = Flask(__name__)
BASE_DIR = "amc"

@app.route('/')
def home():
    amcs = os.listdir(BASE_DIR)
    return render_template("index.html", amcs=amcs)

@app.route('/get_schemes', methods=['POST'])
def get_schemes():
    amc = request.json.get('amc')
    schemes = os.listdir(os.path.join(BASE_DIR, amc))
    return jsonify(schemes)

@app.route('/get_data', methods=['POST'])
def get_data():
    amc = request.json.get('amc')
    scheme = request.json.get('scheme')
    file_path = os.path.join(BASE_DIR, amc, scheme)
    df = pd.read_csv(file_path)
    return jsonify({
        "html": df.to_html(classes='table table-bordered', index=False)
    })

if __name__ == '__main__':
    app.run(debug=True)
