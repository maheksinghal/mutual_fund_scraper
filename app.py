from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil import parser
from flask_caching import Cache
import uuid

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure random key for sessions
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})
BASE_DIR = "amc"
EMAIL_STORAGE = "user_emails.txt"  # File to store user emails
required_cols = {'Name', 'SectorName', 'NoOfShare', 'Month', 'SharesZG', 'MarketValue', 'MarketValueZG', 'HoldingPercentage'}

def get_cache_key(min_shares):
    """Generate a cache key based on file modification times and min_shares."""
    latest_mtime = 0
    for amc_dir in os.listdir(BASE_DIR):
        amc_path = os.path.join(BASE_DIR, amc_dir)
        if os.path.isdir(amc_path):
            for scheme_file in os.listdir(amc_path):
                if scheme_file.endswith('.csv'):
                    file_path = os.path.join(amc_path, scheme_file)
                    mtime = os.path.getmtime(file_path)
                    latest_mtime = max(latest_mtime, mtime)
    return f"all_data_{min_shares}_{int(latest_mtime)}"

@cache.memoize(timeout=3600)  # Cache for 1 hour
def load_all_data(min_shares, cache_key):
    """Load and concatenate all CSV files, using cache_key to ensure freshness."""
    all_dfs = []
    dtypes = {
        'NoOfShare': 'int32',
        'SharesZG': 'float32',
        'MarketValue': 'float32',
        'MarketValueZG': 'float32',
        'HoldingPercentage': 'float32'
    }
    for amc_dir in os.listdir(BASE_DIR):
        amc_path = os.path.join(BASE_DIR, amc_dir)
        if os.path.isdir(amc_path):
            for scheme_file in os.listdir(amc_path):
                if scheme_file.endswith('.csv'):
                    file_path = os.path.join(amc_path, scheme_file)
                    try:
                        df = pd.read_csv(file_path, usecols=required_cols, dtype=dtypes)
                        if required_cols.issubset(df.columns):
                            df = df[df['NoOfShare'] >= min_shares]
                            df['AMC'] = amc_dir
                            df['Scheme'] = scheme_file
                            all_dfs.append(df)
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

def store_email(email):
    """Store user email with timestamp in a file."""
    try:
        with open(EMAIL_STORAGE, 'a') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"{email},{timestamp}\n")
    except Exception as e:
        print(f"Error storing email: {e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.json.get('email')
        if email and '@' in email and '.' in email:  # Basic email validation
            session['user_email'] = email
            store_email(email)
            return jsonify({"success": True, "redirect": url_for('home')})
        return jsonify({"success": False, "message": "Invalid email"})
    return render_template("login.html")

@app.route('/')
def home():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template("index.html")

@app.route('/get_amcs', methods=['GET'])
def get_amcs():
    if 'user_email' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        amcs = sorted([f for f in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, f))])
    except FileNotFoundError:
        amcs = []
    return jsonify(amcs)

@app.route('/get_schemes', methods=['POST'])
def get_schemes():
    if 'user_email' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    amc = request.json.get('amc')
    amc_path = os.path.join(BASE_DIR, amc)
    if not os.path.exists(amc_path):
        return jsonify([])
    
    schemes = [f for f in os.listdir(amc_path) if f.endswith('.csv')]
    return jsonify(schemes)

@app.route('/get_data_for_share_funds', methods=['POST'])
def get_data_for_share_funds():
    if 'user_email' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    share = request.json.get('share')
    min_shares = 1
    try:
        cache_key = get_cache_key(min_shares)
        df = load_all_data(min_shares, cache_key)
        if df.empty:
            return jsonify({"html": "<div class='text-danger'>No valid CSV files found</div>"})

        df = df[df['Name'] == share]
        if df.empty:
            return jsonify({"html": "<div class='text-danger'>No funds found for this share</div>"})

        # Create pivot table for number of shares
        pivot = df.pivot_table(
            index=['AMC', 'Scheme'],
            columns='Month',
            values='NoOfShare',
            aggfunc="sum",
            fill_value=0
        )
        pivot.columns = [str(col).strip() for col in pivot.columns]
        
        # Sort columns by date
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
        pivot.columns.name = None

        # Generate HTML table
        green_shades = [
            "#e9fbe9", "#c8f7c5", "#a3f3a3", "#6de26d", "#36c836", "#1e9f1e", "#107a10", "#075c07", "#033b03"
        ]
        red_shades = [
            "#ffe6e6", "#ffc2c2", "#ff9999", "#ff6b6b", "#ff3b3b", "#e60000", "#990000", "#660000", "#330000"
        ]

        def get_trend_colors(values):
            colors = [green_shades[0]] * len(values)
            trend_count = 1
            direction = 'up'
            for i in range(1, len(values)):
                if pd.notnull(values[i]) and pd.notnull(values[i-1]):
                    if values[i] > values[i-1]:
                        if direction == 'up':
                            trend_count += 1
                        else:
                            trend_count = 1
                            direction = 'up'
                        colors[i] = green_shades[min(trend_count, len(green_shades)-1)]
                    elif values[i] < values[i-1]:
                        if direction == 'down':
                            trend_count += 1
                        else:
                            trend_count = 1
                            direction = 'down'
                        colors[i] = red_shades[min(trend_count, len(red_shades)-1)]
                    else:
                        colors[i] = colors[i-1]
            return colors

        html = f"<h5>Funds Holding {share} (Shares in Lakhs)</h5>"
        html += "<table class='table table-bordered table-striped'><thead><tr>"
        columns = ['AMC', 'Scheme'] + sorted_cols
        for col in columns:
            html += f"<th>{col}</th>"
        html += "</tr></thead><tbody>"

        for _, row in pivot.iterrows():
            html += "<tr>"
            html += f"<td>{row['AMC']}</td><td>{row['Scheme']}</td>"
            values = [row[month] / 100000 for month in sorted_cols]  # Convert to lakhs
            colors = get_trend_colors(values)
            for value, color in zip(values, colors):
                html += f"<td style='background-color:{color}'>{value:.2f} L</td>"
            html += "</tr>"

        html += "</tbody></table>"
        return jsonify({"html": html})
    except Exception as e:
        return jsonify({"html": f"<div class='text-danger'>Error loading funds data: {e}</div>"})

@app.route('/get_funds_for_share', methods=['POST'])
def get_funds_for_share():
    if 'user_email' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    share = request.json.get('share')
    min_shares = 1
    try:
        cache_key = get_cache_key(min_shares)
        df = load_all_data(min_shares, cache_key)
        if df.empty:
            return jsonify([])
        funds = df[df['Name'] == share][['AMC', 'Scheme']].drop_duplicates()
        fund_names = funds.apply(lambda x: f"{x['AMC']} - {x['Scheme']}", axis=1).tolist()
        return jsonify(fund_names)
    except Exception as e:
        return jsonify([])

@app.route('/get_data', methods=['POST'])
def get_data():
    if 'user_email' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    amc = request.json.get('amc')
    scheme = request.json.get('scheme')
    min_shares = int(request.json.get('min_shares', 0))
    view = request.json.get('view', 'holding_percentage')

    dtypes = {
        'NoOfShare': 'int32',
        'SharesZG': 'float32',
        'MarketValue': 'float32',
        'MarketValueZG': 'float32',
        'HoldingPercentage': 'float32'
    }

    if view in ['sector_holding_all', 'share_wise_shares_all']:
        try:
            cache_key = get_cache_key(min_shares)
            df = load_all_data(min_shares, cache_key)
            if df.empty:
                return jsonify({"html": "<div class='text-danger'>No valid CSV files found</div>"})
        except Exception as e:
            return jsonify({"html": f"<div class='text-danger'>Error loading CSVs: {e}</div>"})
    else:
        file_path = os.path.join(BASE_DIR, amc, scheme)
        try:
            df = pd.read_csv(file_path, usecols=required_cols, dtype=dtypes)
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
            aggfunc="sum",
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

    # Create only the necessary pivot table
    if view == 'holding_percentage':
        pivot, month_cols = create_pivot_table('HoldingPercentage')
    elif view == 'sector_holding':
        pivot, month_cols = create_pivot_table('HoldingPercentage', index_cols=['SectorName'])
    elif view == 'sector_holding_all':
        pivot, month_cols = create_pivot_table('HoldingPercentage', index_cols=['SectorName'])
    elif view == 'share_wise_shares_all':
        pivot, month_cols = create_pivot_table('NoOfShare', index_cols=['Name', 'SectorName'])
    elif view == 'consolidated':
        pivot_no_shares, month_cols = create_pivot_table('NoOfShare')
        pivot_shares_zg, _ = create_pivot_table('SharesZG')
        pivot_market_value, _ = create_pivot_table('MarketValue')
        pivot_market_value_zg, _ = create_pivot_table('MarketValueZG')
        pivot_holding_percentage, _ = create_pivot_table('HoldingPercentage')
    else:
        return jsonify({"html": "<div class='text-danger'>Invalid view selected</div>"})

    green_shades = [
        "#e9fbe9", "#c8f7c5", "#a3f3a3", "#6de26d", "#36c836", "#1e9f1e", "#107a10", "#075c07", "#033b03"
    ]
    red_shades = [
        "#ffe6e6", "#ffc2c2", "#ff9999", "#ff6b6b", "#ff3b3b", "#e60000", "#990000", "#660000", "#330000"
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

    def get_trend_colors(values):
        colors = [green_shades[0]] * len(values)
        trend_count = 1
        direction = 'up'
        for i in range(1, len(values)):
            if pd.notnull(values[i]) and pd.notnull(values[i-1]):
                if values[i] > values[i-1]:
                    if direction == 'up':
                        trend_count += 1
                    else:
                        trend_count = 1
                        direction = 'up'
                    colors[i] = green_shades[min(trend_count, len(green_shades)-1)]
                elif values[i] < values[i-1]:
                    if direction == 'down':
                        trend_count += 1
                    else:
                        trend_count = 1
                        direction = 'down'
                    colors[i] = red_shades[min(trend_count, len(red_shades)-1)]
                else:
                    colors[i] = colors[i-1]
        return colors

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
                ("No. of Shares (in L)", pivot_no_shares, False),
                ("Changes in Holding %", pivot_shares_zg, True),
                ("Market Value", pivot_market_value, True),
                ("Changes in Market Value %", pivot_market_value_zg, True),
                ("% of Total Holding", pivot_holding_percentage, True)
            ]

            grouped = pivot_no_shares.groupby(['Share', 'Sector'])
            for (share, sector), group in grouped:
                rowspan = len(metrics)
                for metric_idx, (metric_name, pivot_data, is_decimal) in enumerate(metrics):
                    metric_row = pivot_data[(pivot_data['Share'] == share) & (pivot_data['Sector'] == sector)]
                    html += "<tr>"
                    if metric_idx == 0:
                        html += f"<td rowspan='{rowspan}' style='text-align:center; vertical-align:middle;'>{share}</td>"
                        html += f"<td rowspan='{rowspan}' style='text-align:center; vertical-align:middle;'>{sector}</td>"

                    html += f"<td>{metric_name}</td>"

                    values = [metric_row[month].iloc[0] if not metric_row.empty else 0.0 for month in month_cols]
                    if metric_name == "No. of Shares (in L)":
                        values = [value / 100000 for value in values]  # Convert to lakhs
                    colors = get_trend_colors(values)
                    for value, color in zip(values, colors):
                        display_value = f"{value:.2f}" if is_decimal or metric_name == "No. of Shares (in L)" else str(int(value))
                        if metric_name == "No. of Shares (in L)":
                            display_value += " L"
                        html += f"<td style='background-color:{color}'>{display_value}</td>"
                    html += "</tr>"

        else:
            for _, row in pivot.iterrows():
                html += "<tr>"
                if view in ['sector_holding', 'sector_holding_all']:
                    html += f"<td>{row['Sector']}</td>"
                else:
                    share_cell_class = "share-cell" if view == 'share_wise_shares_all' else ""
                    html += f"<td class='{share_cell_class}'>{row['Share']}</td><td>{row['Sector']}</td>"

                values = [row[month] for month in month_cols]
                if view == 'share_wise_shares_all':
                    values = [value / 100000 for value in values]  # Convert to lakhs
                colors = get_trend_colors(values)
                for value, color in zip(values, colors):
                    display_value = f"{value:.2f} L" if view == 'share_wise_shares_all' else f"{value:.2f}" if is_decimal else str(int(value))
                    html += f"<td style='background-color:{color}'>{display_value}</td>"
                html += "</tr>"

        html += "</tbody></table></div>"
        return html

    if view == 'holding_percentage':
        html = generate_table(pivot, "% of Total Holding", is_decimal=True)
    elif view == 'sector_holding':
        html = generate_table(pivot, "Sector Wise Holding %", is_decimal=True)
    elif view == 'sector_holding_all':
        html = generate_table(pivot, "Sector Wise Holding % (All AMCs)", is_decimal=True)
    elif view == 'share_wise_shares_all':
        html = generate_table(pivot, "Share Wise Number of Shares (All AMCs)")
    elif view == 'consolidated':
        html = generate_table(pivot_no_shares, "Consolidated View", is_consolidated=True, 
                             pivots=[pivot_no_shares, pivot_shares_zg, pivot_market_value, 
                                     pivot_market_value_zg, pivot_holding_percentage])
    else:
        html = "<div class='text-danger'>Invalid view selected</div>"

    return jsonify({"html": html})

if __name__ == '__main__':
    app.run(debug=True)