from flask import Flask, render_template, request, jsonify
import os
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil import parser

app = Flask(__name__)
BASE_DIR = "amc"

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/get_amcs', methods=['GET'])
def get_amcs():
    try:
        amcs = sorted([f for f in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, f))])
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
    view = request.json.get('view', 'holding_percentage')

    required_cols = {'Name', 'SectorName', 'NoOfShare', 'Month', 'SharesZG', 'MarketValue', 'MarketValueZG', 'HoldingPercentage'}

    if view in ['sector_holding_all', 'share_wise_shares_all']:
        try:
            all_dfs = []
            for amc_dir in os.listdir(BASE_DIR):
                amc_path = os.path.join(BASE_DIR, amc_dir)
                if os.path.isdir(amc_path):
                    for scheme_file in os.listdir(amc_path):
                        if scheme_file.endswith('.csv'):
                            file_path = os.path.join(amc_path, scheme_file)
                            df = pd.read_csv(file_path)
                            if not required_cols.issubset(df.columns):
                                continue
                            df = df[df['NoOfShare'] >= min_shares]
                            all_dfs.append(df)
            if not all_dfs:
                return jsonify({"html": "<div class='text-danger'>No valid CSV files found</div>"})
            df = pd.concat(all_dfs, ignore_index=True)
        except Exception as e:
            return jsonify({"html": f"<div class='text-danger'>Error loading CSVs: {e}</div>"})
    else:
        file_path = os.path.join(BASE_DIR, amc, scheme)
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            return jsonify({"html": f"<div class='text-danger'>Error loading CSV: {e}</div>"})
        if not required_cols.issubset(df.columns):
            return jsonify({"html": "<div class='text-danger'>Invalid CSV format: Missing required columns</div>"})
        df = df[df['NoOfShare'] >= min_shares]

    def create_pivot_table(value_col, index_cols=['Name', 'SectorName']):
        pivot = df.pivot_table(
            index=index_cols,
            columns='Month',
            values=value_col,
            aggfunc='sum',
            fill_value=0
        )
        pivot.columns = [str(col).strip() for col in pivot.columns]
        
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
        if len(index_cols) == 2:
            pivot.rename(columns={"Name": "Share", "SectorName": "Sector"}, inplace=True)
        else:
            pivot.rename(columns={"SectorName": "Sector"}, inplace=True)
        pivot.columns.name = None
        return pivot, sorted_cols

    # Create all pivots needed for views
    pivot_no_shares, month_cols = create_pivot_table('NoOfShare')
    pivot_shares_zg, _ = create_pivot_table('SharesZG')
    pivot_market_value, _ = create_pivot_table('MarketValue')
    pivot_market_value_zg, _ = create_pivot_table('MarketValueZG')
    pivot_holding_percentage, _ = create_pivot_table('HoldingPercentage')
    pivot_sector_holding, _ = create_pivot_table('HoldingPercentage', index_cols=['SectorName'])
    pivot_sector_holding_all, _ = create_pivot_table('HoldingPercentage', index_cols=['SectorName'])
    pivot_share_shares_all, _ = create_pivot_table('NoOfShare', index_cols=['Name', 'SectorName'])

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

    def generate_table(pivot, title, is_decimal=False, is_consolidated=False, pivots=None):
        static_cols = ["Share", "Sector"] if view not in ['sector_holding', 'sector_holding_all'] else ["Sector"]
        columns = static_cols + month_cols if not is_consolidated else ["Share", "Sector", "Metric"] + month_cols
        html = f"<h4>{title}</h4>"
        html += "<div style='display:block; overflow-x:auto; width:100%'><table class='table table-bordered table-striped'><thead><tr>"
        
        for col in columns:
            html += f"<th>{col}</th>"
        html += "</tr></thead><tbody>"

        if is_consolidated:
            metrics = [
                ("No. of Shares", pivot_no_shares, False),
                ("Changes in Holding %", pivot_shares_zg, True),
                ("Market Value", pivot_market_value, True),
                ("Changes in Market Value %", pivot_market_value_zg, True),
                ("% of Total Holding", pivot_holding_percentage, True)
            ]
            for _, row in pivot_no_shares.iterrows():
                share, sector = row['Share'], row['Sector']
                for metric_idx, (metric_name, pivot_data, is_decimal) in enumerate(metrics):
                    metric_row = pivot_data[(pivot_data['Share'] == share) & (pivot_data['Sector'] == sector)]
                    if metric_row.empty:
                        html += "<tr>"
                        if metric_idx == 0:
                            html += f"<td>{share}</td><td>{sector}</td>"
                        else:
                            html += "<td></td><td></td>"
                        html += f"<td>{metric_name}</td>"
                        for _ in month_cols:
                            html += "<td style='background-color:#e9fbe9'>0</td>"
                        html += "</tr>"
                        continue
                    html += "<tr>"
                    if metric_idx == 0:
                        html += f"<td>{share}</td><td>{sector}</td>"
                    else:
                        html += "<td></td><td></td>"
                    html += f"<td>{metric_name}</td>"
                    prev_value = None
                    direction = None
                    trend_count = 0
                    prev_color = green_shades[0]
                    for i, month in enumerate(month_cols):
                        current_value = metric_row[month].iloc[0] if not metric_row.empty else 0.0
                        current_value = float(current_value) if pd.notnull(current_value) else 0.0
                        display_value = f"{current_value:.2f}" if is_decimal else str(int(current_value))
                        if i == 0:
                            color = green_shades[0]
                            trend_count = 1
                            direction = 'up'
                        else:
                            if prev_value is not None and pd.notnull(prev_value):
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
                            else:
                                color = green_shades[0]
                        html += f"<td style='background-color:{color}'>{display_value}</td>"
                        prev_value = current_value
                        prev_color = color
                    html += "</tr>"
        else:
            for _, row in pivot.iterrows():
                html += "<tr>"
                if view in ['sector_holding', 'sector_holding_all']:
                    html += f"<td>{row['Sector']}</td>"
                else:
                    html += f"<td>{row['Share']}</td><td>{row['Sector']}</td>"
                prev_value = None
                direction = None
                trend_count = 0
                prev_color = green_shades[0]
                for i, month in enumerate(month_cols):
                    current_value = row[month]
                    current_value = float(current_value) if pd.notnull(current_value) else 0.0
                    display_value = f"{current_value:.2f}" if is_decimal else str(int(current_value))
                    if i == 0:
                        color = green_shades[0]
                        trend_count = 1
                        direction = 'up'
                    else:
                        if prev_value is not None and pd.notnull(prev_value):
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
                        else:
                            color = green_shades[0]
                    html += f"<td style='background-color:{color}'>{display_value}</td>"
                    prev_value = current_value
                    prev_color = color
                html += "</tr>"

        html += "</tbody></table></div>"
        return html

    if view == 'holding_percentage':
        html = generate_table(pivot_holding_percentage, "% of Total Holding", is_decimal=True)
    elif view == 'sector_holding':
        html = generate_table(pivot_sector_holding, "Sector Wise Holding %", is_decimal=True)
    elif view == 'sector_holding_all':
        html = generate_table(pivot_sector_holding_all, "Sector Wise Holding % (All AMCs)", is_decimal=True)
    elif view == 'share_wise_shares_all':
        html = generate_table(pivot_share_shares_all, "Share Wise Number of Shares (All AMCs)")
    elif view == 'consolidated':
        html = generate_table(pivot_no_shares, "Consolidated View", is_consolidated=True, 
                            pivots=[pivot_no_shares, pivot_shares_zg, pivot_market_value, 
                                   pivot_market_value_zg, pivot_holding_percentage])
    else:
        html = "<div class='text-danger'>Invalid view selected</div>"

    return jsonify({"html": html})

if __name__ == '__main__':
    app.run(debug=True)