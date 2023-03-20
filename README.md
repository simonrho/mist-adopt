# MIST ADOPT
This script automates the adoption of Juniper devices to the Mist platform. It reads device information from an Excel file, fetches the adoption configuration from the Mist API, and pushes the configuration to the devices using NETCONF.

## Requirements
* Python 3
* Libraries: `pandas`, `openpyxl`, `requests`, `ncclient`, and `concurrent.futures`
* Excel file with device information
* Mist API key

## Installation
1. Make sure you have Python 3 installed.
2. Install the required libraries using pip:

```bash
pip install pandas openpyxl requests ncclient
```

## Usage

```bash
python mist-adopt.py <excel_file> [-k] [--keep-phone-home] [-t] [--max-threads] [-a] [--api-key]
```

### Arguments
* `<excel_file>`: Path to the Excel file containing device information (org_id, site_id, ip, user_id, password).
* `-k`, `--keep-phone-home`: Keep the 'delete system phone-home' command in the configuration (optional).
* `-t`, `--max-threads`: Maximum number of concurrent threads (default: 10) (optional).
* `-a`, `--api-key`: Mist API key (optional).

### Excel file format
The Excel file should contain the following columns:

* `org_id`: Mist organization ID.
* `site_id`: Mist site ID.
* `ip`: Device IP address.
* `user_id`: Device username.
* `password`: Device password.

## Example
```bash
python mist-adopt.py devices.xlsx -t 5 -a <your_mist_api_key>
```

## Notes
The script will use the Mist API key from the environment variable "MIST_API_KEY" if available. 
If not found, it will try to read the API key from the configuration file located at "~/.mist/config.ini". 
If the API key is not found in either of these locations, the user must provide it using the `-a` or `--api-key` option.
If the `--keep-phone-home` option is not specified, the script will remove the 'delete system phone-home' command 
from the configuration before pushing it to the devices.