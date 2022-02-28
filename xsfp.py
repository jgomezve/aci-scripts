# Import Python libaries
import urllib3
import requests
import argparse
import csv

# Disable self-signed certificate warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if __name__ == "__main__":

    # Get user input
    parser = argparse.ArgumentParser(description="Read SFP types")
    parser.add_argument('-ip', '--apic_ip', required=True)
    parser.add_argument('-usr', '--username', required=True)
    parser.add_argument('-pwd', '--password', required=True)
    args = parser.parse_args()

    apic_ip = args.apic_ip
    username = args.username
    password = args.password

    # Define Authentication payload. APIC Object aaaUser
    apic_login = {
        "aaaUser": {
            "attributes": {
                "name": username,
                "pwd": password,
            }
        }
    }

    # Create a HTTPS session
    apic_session = requests.Session()

    # Send POST call to the Authentication endpoint
    response = apic_session.post(f"https://{apic_ip}/api/aaaLogin.json", verify=False, json=apic_login)

    # Verify response
    if response.status_code != 200:
        # If failed exit
        print("Authentication failed")
        exit(0)
    else:
        # If sucessfull, save the Authorization Bearer
        bearer = response.json()["imdata"][0]["aaaLogin"]["attributes"]["token"]
        headers = {"Authorization": f"Bearer {bearer}"}

    # Send a GET call to the ethpmFcot endpoint. Include the Authentication Header
    response = apic_session.get(f"https://{apic_ip}/api/node/class/ethpmFcot.json", verify=False, headers=headers)

    f = open('./xsfp.csv', 'w')
    writer = csv.writer(f)

    writer.writerow(["dn", "actualType", "guiCiscoPID", "guiCiscoPN", "guiName", "guiPN"])
    for eth in response.json()["imdata"]:
        if eth['ethpmFcot']['attributes']['actualType'] != "unknown":
            row = [eth['ethpmFcot']['attributes']['dn'], eth['ethpmFcot']['attributes']['actualType'], eth['ethpmFcot']['attributes']['guiCiscoPID'], eth['ethpmFcot']['attributes']['guiCiscoPN'], eth['ethpmFcot']['attributes']['guiName'], eth['ethpmFcot']['attributes']['guiPN']]
            writer.writerow(row)
    f.close()
    
