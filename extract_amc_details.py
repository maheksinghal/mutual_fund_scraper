import requests
import os
import pandas as pd
from datetime import datetime

# Possible values for 'MfNAVChangePeriodType' 1, 7, 30, 90,180, 365, 730, 1095, 1852 <values are in days>
# example to list last 1 year sceheme set value as '365'
MfNAVChangePeriodType = 365

# ex 10 means script will scrape first 10 AMC
NUMBER_AMC_TO_SCRAPE = 2

# Represent month of which MF data will be scrapped
MF_HOLDING_DATE = "2025-05-31"

# PAth of where data will be dumped
AMC_RECORD = "amc"

def get_mf_domestic_holdings(mf_scheme_id, mf_holding_date):
    base_url = "https://api.stockedge.com/Api/MfSchemeDashboardApi/GetDomesticEquityHoldings"
    url = f"{base_url}/{mf_scheme_id}/{mf_holding_date}"

    params = {
        "page": 1,
        "pageSize": 1000, # Getting top 1000 holding of the MF. Update the value in case of holdings are more then 1000
        "lang": "en"
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            holdings_records = response.json()
            print("Number of holding in scheme: ", len(holdings_records))
            return holdings_records

        else:
            print(f"failed to get holdings for MF scheme '{mf_scheme_id}' for date '{mf_holding_date}'. Status Code: {response.status_code}")
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"failed to get holdings for MF scheme '{mf_scheme_id}' for date '{mf_holding_date}'. Error: {e}")
    return []

def write_data_to_excel(mf_bank, mf_scheme_name ,holdings_records):
    data_frame = pd.DataFrame(holdings_records)
    date_str = datetime.today().strftime('%Y-%m-%d')
    data_frame.to_csv(f"{AMC_RECORD}/{mf_bank}/{mf_scheme_name}_{date_str}.csv", index=False)
    print("Crated file for the scheme")
    

def get_mf_schema_details(mf_id):
    base_url = "https://api.stockedge.com/Api/MfAmcDashboardApi/GetPrimaryMfSchemeListByAmc"
    url = f"{base_url}/{mf_id}"
    params = {
        "MfSchemeAssetTypeID": "1",
        "MfNAVChangePeriodType": MfNAVChangePeriodType,
        "page": 1,
        "pageSize": 1000, # Get top 1000 MF scheme
        "lang": "en"
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            mf__scheme_list = response.json()
            return mf__scheme_list

        else:
            print(f"failed to list MF schemes'. Status Code: {response.status_code}")
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"failed to list MF schemes'. Error: {e}")
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
        if response.status_code == 200:
            mf_list = response.json()
            print(len(mf_list))
            return mf_list

        else:
            print(f"failed to list MF'. Status Code: {response.status_code}")
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"failed to list MF'. Error: {e}")
    return []


def create_folder(path):
    try:
        if not os.path.isdir(path):
            os.mkdir(path)
    except OSError as e:
        print(f"failed to create '{path}' directory, error: {e}")
        raise

def main():
    try:
        create_folder(AMC_RECORD)
        amc_list = get_amc_list()
        print(f"Data will be pulled from '{len(amc_list)}' AMC")
        for amc in amc_list:
            # getting list of scheme listed by banks
            amc_name = amc["Name"]
            amc_id = amc["ID"]
            create_folder(f"{AMC_RECORD}/{amc_name}")

            mf_scheme_records = get_mf_schema_details(amc_id)
            print(f"NUMBER OF SCHEMES in {amc_name}: {len(mf_scheme_records)}")
            for mf_scheme in mf_scheme_records:
                mf_scheme_name = mf_scheme["Name"]
                mf_scheme_id = mf_scheme["ID"]
                print(f"-------{mf_scheme_name}------")

                # Getting stocks holdings for mutual fund scheme
                holdings_records = get_mf_domestic_holdings(mf_scheme_id, MF_HOLDING_DATE)
                write_data_to_excel(amc_name, mf_scheme_name, holdings_records)
                print()
    except Exception as e:
        print(f"failed to load details of {amc_name}. error: {e}")

if __name__ == "__main__":
    main()