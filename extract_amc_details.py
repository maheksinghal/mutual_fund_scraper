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
    params = {"page": 1, "pageSize": NUMBER_AMC_TO_SCRAPE, "lang": "en"}
    try:
        response = requests.get(url, params=params)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def get_mf_schema_details(mf_id):
    url = f"https://api.stockedge.com/Api/MfAmcDashboardApi/GetPrimaryMfSchemeListByAmc/{mf_id}"
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

def get_mf_domestic_holdings(mf_scheme_id, mf_holding_date, check_only=False):
    url = f"https://api.stockedge.com/Api/MfSchemeDashboardApi/GetDomesticEquityHoldings/{mf_scheme_id}/{mf_holding_date}"
    params = {"page": 1, "pageSize": 1000, "lang": "en"}
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
    except:
        return []
    return []

def find_latest_available_date_in_last_7_days(mf_scheme_id, month_start_date):
    next_month = month_start_date.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    
    # Check last 7 days of the month only
    for i in range(7):
        date_to_try = (last_day - timedelta(days=i)).strftime('%Y-%m-%d')
        if get_mf_domestic_holdings(mf_scheme_id, date_to_try, check_only=True):
            return date_to_try
    return None

def add_missing_month_to_existing_files():
    today = datetime.today()
    if today.day < 5:
        today = today.replace(day=1) - timedelta(days=1)
    latest_month_date = today.replace(day=1)
    target_month = latest_month_date.strftime("%b-%Y")

    amc_list = get_amc_list()

    found_valid_date = None  # to track first successful holding date

    for amc in amc_list:
        amc_name = re.sub(r'[\\/*?:"<>|]', "_", amc["Name"])
        amc_id = amc["ID"]
        print(f"\n Processing AMC: {amc_name} (ID: {amc_id})")
        folder_path = f"{AMC_RECORD}/{amc_name}"

        mf_scheme_records = get_mf_schema_details(amc_id)
        for mf_scheme in mf_scheme_records:
            scheme_name = re.sub(r'[\\/*?:"<>|]', "_", mf_scheme["Name"])
            scheme_id = mf_scheme["ID"]
            print(f"\n Processing Scheme: {scheme_name} (ID: {scheme_id})")
            file_path = f"{folder_path}/{scheme_name}.csv"

            if not os.path.exists(file_path):
                continue

            try:
                df = pd.read_csv(file_path)
            except:
                continue

            if target_month in df["Month"].values:
                print(f"{target_month} already exists in {scheme_name}")
                continue

            if not found_valid_date:
                latest_data_date = find_latest_available_date_in_last_7_days(scheme_id, latest_month_date)
                if not latest_data_date:
                    print("No data found in last 7 days for first scheme — skipping further processing.")
                    return  # Exit early — skip all other AMCs
                found_valid_date = latest_data_date
            else:
                latest_data_date = found_valid_date

            new_data = get_mf_domestic_holdings(scheme_id, latest_data_date)
            if not new_data:
                continue

            for record in new_data:
                record["Month"] = target_month

            new_df = pd.DataFrame(new_data)
            updated_df = pd.concat([new_df, df], ignore_index=True)
            updated_df.to_csv(file_path, index=False)
            print(f"Added {target_month} to {file_path}")

if __name__ == "__main__":
    add_missing_month_to_existing_files()
