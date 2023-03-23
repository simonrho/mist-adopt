#!/usr/bin/env python3
import argparse
import configparser
import pandas as pd
import requests
import numpy as np
from tabulate import tabulate
import sys
import os

from ncclient import manager
import concurrent.futures



def dump_excel_file(file_name):
    try:
        # Read the Excel file
        df = pd.read_excel(file_name)

        # Mask password fields with asterisks
        for col in df.columns:
            if 'password' in col.lower():
                df[col] = df[col].apply(lambda x: len(str(x)) * '*')

        # Replace empty cells with "Empty"
        df.replace(np.nan, 'Empty', inplace=True)

        # Print the data in a table format
        print(tabulate(df, headers='keys', tablefmt='psql'))

    except FileNotFoundError:
        print(f"Error: file {file_name} not found")
        sys.exit(1)


def read_excel(file_name):
    df = pd.read_excel(file_name, engine="openpyxl")
    return df.drop_duplicates(subset="ip", keep="last")


def fetch_mist_config(mist_api_key, org_id, site_id=None, remove_phone_home=True):
    base_url = "https://api.mist.com/api/v1"
    url = f"{base_url}/orgs/{org_id}/ocdevices/outbound_ssh_cmd"

    if site_id and not pd.isna(site_id):
        url += f"?site_id={site_id}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {mist_api_key}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        cmd = response.json()["cmd"]
        if remove_phone_home:
            cmd = "\n".join(line for line in cmd.split("\n") if "delete system phone-home" not in line)
        return cmd.split("\n")
    else:
        return f"Failed to fetch adoption command from MIST API: {response.text}"


def get_mist_api_key_from_env():
    env_var_name = "MIST_API_KEY"
    if env_var_name in os.environ:
        return os.environ[env_var_name]
    else:
        raise ValueError(f"Environment variable '{env_var_name}' not found.")


def get_mist_api_key_from_config():
    config_file_path = os.path.expanduser("~/.mist/config.ini")
    config = configparser.ConfigParser()

    if os.path.exists(config_file_path):
        config.read(config_file_path)
        if "Mist" in config.sections() and "api_key" in config["Mist"]:
            return config["Mist"]["api_key"]
        else:
            raise ValueError(f"API key not found in config file '{config_file_path}'.")
    else:
        raise FileNotFoundError(f"Config file '{config_file_path}' not found.")


def push_config(device_info, config_commands):
    ip, user_id, password = device_info
    try:
        m = manager.connect(
            host=ip,
            username=user_id,
            password=password,
            timeout=60,
            hostkey_verify=False,
            device_params={"name": "junos"},
            allow_agent=False,
            look_for_keys=False
        )

        commit_result = m.load_configuration(action='set', config=config_commands)
        m.commit()
        m.close_session()

        if commit_result.find(".//ok") is not None:
            return "OK"
        else:
            return "Error: Commit failed"
    except Exception as e:
        return f"Error: Unable to establish NETCONF connection with {ip}. Reason: {str(e)}"


def worker(mist_api_key, device_info, remove_phone_home):
    org_id, site_id, ip, user_id, password = device_info
    config_commands = fetch_mist_config(mist_api_key, org_id, site_id, remove_phone_home=remove_phone_home)
    if isinstance(config_commands, str):  # If an error message is returned
        return ip, config_commands
    else:
        result = push_config((ip, user_id, password), config_commands)
        return ip, result


def main():
    parser = argparse.ArgumentParser(description="Juniper device configuration script")
    parser.add_argument("excel_file", help="Excel file containing device information (org_id, site_id, ip, user_id, password)")
    parser.add_argument("-k", "--keep-phone-home", action="store_true", help="Keep 'delete system phone-home' command in the configuration")
    parser.add_argument("-t", "--max-threads", type=int, default=10, help="Maximum number of concurrent threads (default: 10)")
    parser.add_argument("-a", "--api-key", help="Mist API key (optional)")

    args = parser.parse_args()

    dump_excel_file(args.excel_file)

    try:
        device_data = read_excel(args.excel_file)
    except FileNotFoundError:
        print(f"Error: Cannot open file '{args.excel_file}'. Please check the file path.")
        return
    except Exception as e:
        print(f"Error: {str(e)}")
        return

    required_fields = {"org_id", "site_id", "ip", "user_id", "password"}
    if not required_fields.issubset(device_data.columns):
        print(f"Error: Invalid Excel file format. Required fields: {', '.join(required_fields)}")
        return

    mist_api_key = None
    try:
        mist_api_key = get_mist_api_key_from_env()
    except ValueError:
        try:
            mist_api_key = get_mist_api_key_from_config()
        except (FileNotFoundError, ValueError):
            if args.api_key:
                mist_api_key = args.api_key
            else:
                print("Error: Mist API key not found in environment variable, config file, or CLI option.")
                return

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_threads) as executor:
        future_to_device = {
            executor.submit(worker, mist_api_key, row, not args.keep_phone_home): row["ip"] for _, row in device_data.iterrows()
        }

        results = {}
        for future in concurrent.futures.as_completed(future_to_device):
            ip = future_to_device[future]
            try:
                result = future.result()
            except Exception as e:
                result = f"Error: {str(e)}"
            results[ip] = result

    for ip in sorted(results):
        print(f"{ip}: {results[ip][1]}")

if __name__ == "__main__":
    main()
