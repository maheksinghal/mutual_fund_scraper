from flask import Flask, render_template, request, jsonify
import os
import pandas as pd
import numpy as np
from datetime import datetime

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
    amc = request.json.get('amc')
    scheme = request.json.get('scheme')
    min_shares = int(request.json.get('min_shares', 0))
    view = request.json.get('view', 'no_of_share')  # Default to no_of_share
    file_path = os.path.join(BASE_DIR, amc, scheme)

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        return jsonify({"html": f"<div class='text-danger'>Error loading CSV: {e}</div>"})

    required_cols = {'Name', 'SectorName', 'NoOfShare', 'Month', 'SharesZG', 'MarketValue', 'MarketValueZG', 'HoldingPercentage'}
    if not required_cols.issubset(df.columns):
        return jsonify({"html": "<div class='text-danger'>Invalid CSV format: Missing required columns</div>"})

    # Filter by min_shares based on NoOfShare
    df = df[df['NoOfShare'] >= min_shares]

    # Helper function to create pivot table
    def create_pivot_table(value_col):
        pivot = df.pivot_table(
            index=['Name', 'SectorName'],
            columns='Month',
            values=value_col,
            aggfunc='sum',
            fill_value=0
        )
        pivot.columns = [str(col).strip() for col in pivot.columns]

        # Sort columns by parsed dates
        def try_parse(col):
            try:
                dt = parser.parse(col, dayfirst=False, fuzzy=True)
                return (col, dt)
            except:
                return None

        parsed = list(filter(None, map(try_parse, pivot.columns)))
        sorted_cols = [col for col, _ in sorted(parsed, key=lambda x: x[1])]
        pivot = pivot[sorted_cols]
        pivot.reset_index(inplace=True)
        pivot.rename(columns={"Name": "Share", "SectorName": "Sector"}, inplace=True)
        pivot.columns.name = None
        return pivot, sorted_cols

    # Create pivot tables
    pivot_no_shares, month_cols = create_pivot_table('NoOfShare')
    pivot_shares_zg, _ = create_pivot_table('SharesZG')
    pivot_market_value, _ = create_pivot_table('MarketValue')
    pivot_market_value_zg, _ = create_pivot_table('MarketValueZG')
    pivot_holding_percentage, _ = create_pivot_table('HoldingPercentage')

    static_cols = ["Share", "Sector"]
    columns = static_cols + month_cols

    green_shades = [
        "#e9fbe9", "#c8f7c5", "#a3f3a3", "#6de26d", "#36c836", "#1e9f1e", "#107a10"
    ]
    red_shades = [
        "#ffe6e6", "#ffc2c2", "#ff9999", "#ff6b6b", "#ff3b3b", "#e60000", "#990000"
    ]

    def get_cumulative_color(trend_count, direction):
        max_index = len(green_shades) - 1
        trend_count = min(trend_count, max_index)
        if direction == 'up':
            return green_shades[trend_count]
        elif direction == 'down':
            return red_shades[trend_count]
        else:
            return green_shades[0]

    def generate_table(pivot, title, is_decimal=False):
        html = f"<h4>{title}</h4>"
        html += "<div style='display:block; overflow-x:auto; width:100%'><table class='table table-bordered table-striped'><thead><tr>"
        for col in columns:
            html += f"<th>{col}</th>"
        html += "</tr></thead><tbody>"

        for _, row in pivot.iterrows():
            html += "<tr>"
            html += f"<td>{row['Share']}</td><td>{row['Sector']}</td>"

            prev_value = None
            direction = None
            trend_count = 0
            prev_color = green_shades[0]

            for i, month in enumerate(month_cols):
                current_value = row[month]
                # Round to 2 decimal places for SharesZG, MarketValue, MarketValueZG, and HoldingPercentage
                display_value = f"{current_value:.2f}" if is_decimal else str(int(current_value))
                if i == 0:
                    color = green_shades[0]
                    trend_count = 1
                    direction = 'up'
                else:
                    if current_value > prev_value:
                        if direction == 'up':
                            trend_count += 1
                        else:
                            trend_count = 1
                            direction = 'up'
                        color = get_cumulative_color(trend_count, direction)
                    elif current_value < prev_value:
                        if direction == 'down':
                            trend_count += 1
                        else:
                            trend_count = 1
                            direction = 'down'
                        color = get_cumulative_color(trend_count, direction)
                    else:
                        color = prev_color

                html += f"<td style='background-color:{color}'>{display_value}</td>"
                prev_value = current_value
                prev_color = color

            html += "</tr>"

        html += "</tbody></table></div>"
        return html

    # Select table based on view
    if view == 'no_of_share':
        html = generate_table(pivot_no_shares, "Number of Shares")
    elif view == 'holding_change':
        html = generate_table(pivot_shares_zg, "Changes in Holding %", is_decimal=True)
    elif view == 'market_value':
        html = generate_table(pivot_market_value, "Market Value", is_decimal=True)
    elif view == 'market_value_zg':
        html = generate_table(pivot_market_value_zg, "Changes in Market Value %", is_decimal=True)
    elif view == 'holding_percentage':
        html = generate_table(pivot_holding_percentage, "% of Total Holding", is_decimal=True)
    else:
        html = "<div class='text-danger'>Invalid view selected</div>"

    return jsonify({"html": html})

if __name__ == '__main__':
    app.run(debug=True)
