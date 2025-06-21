from flask import Flask, render_template, request, jsonify
import os
import pandas as pd

app = Flask(__name__)
BASE_DIR = "amc"

@app.route('/')
def home():
    try:
        amcs = [f for f in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, f))]
    except FileNotFoundError:
        amcs = []
    return render_template("index.html", amcs=amcs)

@app.route('/get_schemes', methods=['POST'])
def get_schemes():
    amc = request.json.get('amc')
    amc_path = os.path.join(BASE_DIR, amc)
    if not os.path.exists(amc_path):
        return jsonify([])
    
    schemes = [f for f in os.listdir(amc_path) if f.endswith('.csv')]
    return jsonify(schemes)

@app.route('/get_data', methods=['POST'])
def get_data():
    amc = request.json.get('amc')
    scheme = request.json.get('scheme')
    file_path = os.path.join(BASE_DIR, amc, scheme)

    if not os.path.isfile(file_path):
        return jsonify({"html": "<p class='text-danger'>Data not found.</p>"})

    try:
        df = pd.read_csv(file_path)

        # Optional: Sort by Month (if present)
        if "Month" in df.columns:
            df['Month'] = pd.to_datetime(df['Month'], format="%b-%Y", errors='coerce')
            df = df.sort_values(by="Month").fillna("")

        df_html = df.to_html(classes='table table-bordered table-hover', index=False, escape=False)
        return jsonify({"html": df_html})

    except Exception as e:
        return jsonify({"html": f"<p class='text-danger'>Error loading data: {str(e)}</p>"})

if __name__ == '__main__':
    app.run(debug=True)
