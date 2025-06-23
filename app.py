from flask import Flask, render_template, request, jsonify
import os
import pandas as pd

app = Flask(__name__)
BASE_DIR = "amc"

@app.route('/')
def home():
    return render_template("index.html")  # No amcs passed anymore

@app.route('/get_amcs', methods=['GET'])
def get_amcs():
    try:
        amcs = [f for f in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, f))]
    except FileNotFoundError:
        amcs = []
    return jsonify(amcs)

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
    min_shares = int(request.json.get('min_shares', 0))
    file_path = os.path.join(BASE_DIR, amc, scheme)

    df = pd.read_csv(file_path)

    if 'HoldingShares' not in df.columns:
        return jsonify({"html": "<div class='text-danger'>Invalid CSV format</div>"})

    # Filter by min shares
    df = df[df['HoldingShares'] >= min_shares]

    # Pivot: Show shares per month
    pivot = df.pivot_table(index=['Name', 'Sector'], columns='Month', values='HoldingShares', aggfunc='sum', fill_value=0)
    pivot.reset_index(inplace=True)
    pivot.columns.name = None

    return jsonify({
        "html": pivot.to_html(classes='table table-bordered table-striped', index=False)
    })

if __name__ == '__main__':
    app.run(debug=True)
