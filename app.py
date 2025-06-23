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

from dateutil import parser  # <-- add this

@app.route('/get_data', methods=['POST'])
def get_data():
    import pandas as pd
    import numpy as np
    from datetime import datetime

    amc = request.json.get('amc')
    scheme = request.json.get('scheme')
    min_shares = int(request.json.get('min_shares', 0))
    file_path = os.path.join(BASE_DIR, amc, scheme)

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        return jsonify({"html": f"<div class='text-danger'>Error loading CSV: {e}</div>"})

    required_cols = {'Name', 'SectorName', 'NoOfShare', 'Month'}
    if not required_cols.issubset(df.columns):
        return jsonify({"html": "<div class='text-danger'>Invalid CSV format: Missing required columns</div>"})

    df = df[df['NoOfShare'] >= min_shares]

    # Pivot table
    pivot = df.pivot_table(
        index=['Name', 'SectorName'],
        columns='Month',
        values='NoOfShare',
        aggfunc='sum',
        fill_value=0
    )

    # Step 1: Ensure clean column names
    pivot.columns = [str(col).strip() for col in pivot.columns]

    # Step 2: Safely parse and sort columns using dateutil
    def try_parse(col):
        try:
            dt = parser.parse(col, dayfirst=False, fuzzy=True)
            return (col, dt)
        except:
            return None

    parsed = list(filter(None, map(try_parse, pivot.columns)))
    sorted_cols = [col for col, _ in sorted(parsed, key=lambda x: x[1])]

    # Step 3: Reorder
    pivot = pivot[sorted_cols]

    # Final formatting
    pivot.reset_index(inplace=True)
    pivot.rename(columns={"Name": "Share", "SectorName": "Sector"}, inplace=True)
    pivot.columns.name = None

    html_table = pivot.to_html(classes='table table-bordered table-striped', index=False)
    html = f"<div style='display:block; overflow-x:auto; width:100%'>{html_table}</div>"

    return jsonify({"html": html})



if __name__ == '__main__':
    app.run(debug=True)
