import requests
import os
import pandas as pd
from datetime import datetime, timedelta
import re

MfNAVChangePeriodType = 365
NUMBER_AMC_TO_SCRAPE = 1000
AMC_RECORD = "amc"

def get_amc_list():
    url = "https://api.stockedge.com/Api/MfAmcDashboardApi/GetMfAmcList"
    params = {
        "page": 1,
        "pageSize": NUMBER_AMC_TO_SCRAPE,
        "lang": "en"
    }
    try:
        response = requests.get(url, params=params)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def get_mf_schema_details(mf_id):
    base_url = "https://api.stockedge.com/Api/MfAmcDashboardApi/GetPrimaryMfSchemeListByAmc"
    url = f"{base_url}/{mf_id}"
    params = {
        "MfSchemeAssetTypeID": "1",
        "MfNAVChangePeriodType": MfNAVChangePeriodType,
        "page": 1,
        "pageSize": 1000,
        "lang": "en"
    }
    try:
        response = requests.get(url, params=params)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def find_latest_available_date(mf_scheme_id, days_to_check=31):
    for i in range(days_to_check):
        date_to_try = (datetime.today() - timedelta(days=i)).strftime('%Y-%m-%d')
        holdings = get_mf_domestic_holdings(mf_scheme_id, date_to_try, check_only=True)
        if holdings:
            print(f"Found data on: {date_to_try}")
            return date_to_try
    print("Could not find recent available data.")
    return None

def get_mf_domestic_holdings(mf_scheme_id, mf_holding_date, check_only=False):
    base_url = "https://api.stockedge.com/Api/MfSchemeDashboardApi/GetDomesticEquityHoldings"
    url = f"{base_url}/{mf_scheme_id}/{mf_holding_date}"
    params = {
        "page": 1,
        "pageSize": 1000,
        "lang": "en"
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            return data if check_only else data
        else:
            return [] if check_only else []
    except Exception as e:
        print(f"Error checking scheme {mf_scheme_id}: {e}")
        return [] if check_only else []

def get_monthly_dates(months=6):
    today = datetime.today()
    dates = []
    for i in range(months):
        date = (today.replace(day=1) - timedelta(days=1))
        dates.append(date.replace(day=1).strftime('%Y-%m-%d'))
        today = date
    return dates[::-1]  # From oldest to newest

def create_folder(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"Error creating folder {path}: {e}")

def write_combined_data_to_csv(mf_bank, mf_scheme_name, all_data):
    safe_scheme_name = re.sub(r'[\\/*?:"<>|]', "_", mf_scheme_name)
    safe_mf_bank = re.sub(r'[\\/*?:"<>|]', "_", mf_bank)

    df = pd.DataFrame(all_data)
    folder_path = f"{AMC_RECORD}/{safe_mf_bank}"
    file_path = f"{folder_path}/{safe_scheme_name}.csv"
    create_folder(folder_path)

    df.to_csv(file_path, index=False)
    print(f"Saved: {file_path}")

def main():
    create_folder(AMC_RECORD)
    amc_list = get_amc_list()
    print(f"Pulling data from {len(amc_list)} AMCs")

    monthly_dates = get_monthly_dates(6)  # Last 6 months

    for amc in amc_list:
        amc_name = amc["Name"]
        amc_id = amc["ID"]
        print(f"\n AMC: {amc_name}")

        create_folder(f"{AMC_RECORD}/{amc_name}")
        mf_scheme_records = get_mf_schema_details(amc_id)

        for mf_scheme in mf_scheme_records:
            mf_scheme_name = mf_scheme["Name"]
            mf_scheme_id = mf_scheme["ID"]
            print(f"→ Scheme: {mf_scheme_name}")

            all_data = []
            for month_date in monthly_dates:
                date_found = find_latest_available_date(mf_scheme_id)
                if not date_found:
                    print(f"No data for {mf_scheme_name} in {month_date}")
                    continue

                holdings_records = get_mf_domestic_holdings(mf_scheme_id, date_found)
                if holdings_records:
                    for record in holdings_records:
                        record["Month"] = datetime.strptime(date_found, "%Y-%m-%d").strftime("%b-%Y")
                        all_data.append(record)

            if all_data:
                write_combined_data_to_csv(amc_name, mf_scheme_name, all_data)

if __name__ == "__main__":
    main()
