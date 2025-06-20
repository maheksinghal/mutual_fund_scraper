import requests
import os
import pandas as pd
from datetime import datetime, timedelta
import re

MfNAVChangePeriodType = 365
NUMBER_AMC_TO_SCRAPE = 1000
AMC_RECORD = "amc"

# Shared date for all schemes
latest_common_date = None

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


def write_data_to_excel(mf_bank, mf_scheme_name, holdings_records):
    # Sanitize scheme name to make it a safe file name
    safe_scheme_name = re.sub(r'[\\/*?:"<>|]', "_", mf_scheme_name)
    safe_mf_bank = re.sub(r'[\\/*?:"<>|]', "_", mf_bank)

    data_frame = pd.DataFrame(holdings_records)
    date_str = datetime.today().strftime('%Y-%m-%d')
    folder_path = f"{AMC_RECORD}/{safe_mf_bank}"
    file_path = f"{folder_path}/{safe_scheme_name}_{date_str}.csv"

    # Ensure directory exists
    create_folder(folder_path)

    data_frame.to_csv(file_path, index=False)
    print(f"Created file: {file_path}")


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

def create_folder(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"Error creating folder {path}: {e}")

def main():
    global latest_common_date
    create_folder(AMC_RECORD)
    amc_list = get_amc_list()
    print(f"Pulling data from {len(amc_list)} AMCs")

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

            # Only check for the latest date once
            if not latest_common_date:
                latest_common_date = find_latest_available_date(mf_scheme_id)

            if not latest_common_date:
                print(f"No recent data for {mf_scheme_name}")
                continue

            holdings_records = get_mf_domestic_holdings(mf_scheme_id, latest_common_date)
            if holdings_records:
                write_data_to_excel(amc_name, mf_scheme_name, holdings_records)

if __name__ == "__main__":
    main()
