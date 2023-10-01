import json, requests, time, hashlib, string, threading, re, configparser, os
from passlib.hash import argon2
from random import choice, randrange

import argparse
import configparser


# Set up argument parser
parser = argparse.ArgumentParser(description="Process optional address and worker arguments.")
parser.add_argument('--proxy', type=str, help='The proxy address to send work.')
parser.add_argument('--worker', type=int, help='The worker id to use.')

args = parser.parse_args()

proxy = args.proxy
worker_id = args.worker
gpu_mode = True # GPU Only

# For example, to print the values
print(f'args from command: Proxy Address: {proxy}, Worker ID: {worker_id}')
print(f'DEV-FEE-ON(1s): Set by proxy')

# Load the configuration file
config = configparser.ConfigParser()
config_file_path = 'miner_config.conf'

if os.path.exists(config_file_path):
    config.read(config_file_path)
else:
    raise FileNotFoundError(f"The configuration file {config_file_path} was not found.")

# Override account from config file with command line argument if provided
if not args.proxy:
    # Ensure that the required settings are present
    required_settings = ['difficulty', 'memory_cost', 'proxy']
    if not all(key in config['Settings'] for key in required_settings):
        missing_keys = [key for key in required_settings if key not in config['Settings']]
        raise KeyError(f"Missing required settings: {', '.join(missing_keys)}")
    proxy = config['Settings']['proxy']

# Access other settings
difficulty = int(config['Settings']['difficulty'])
memory_cost = int(config['Settings']['memory_cost'])

def hash_value(value):
    return hashlib.sha256(value.encode()).hexdigest()

def build_merkle_tree(elements, merkle_tree={}):
    if len(elements) == 1:
        return elements[0], merkle_tree
    new_elements = []
    for i in range(0, len(elements), 2):
        left = elements[i]
        right = elements[i + 1] if i + 1 < len(elements) else left
        combined = left + right
        new_hash = hash_value(combined)
        merkle_tree[new_hash] = {'left': left, 'right': right}
        new_elements.append(new_hash)
    return build_merkle_tree(new_elements, merkle_tree)

from datetime import datetime
def is_within_five_minutes_of_hour():
    timestamp = datetime.now()
    minutes = timestamp.minute
    return 0 <= minutes < 5 or 55 <= minutes < 60

class Block:
    def __init__(self, index, prev_hash, data, valid_hash, random_data, attempts):
        self.index = index
        self.prev_hash = prev_hash
        self.data = data
        self.valid_hash = valid_hash
        self.random_data = random_data
        self.attempts = attempts
        self.timestamp = time.time()
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        sha256 = hashlib.sha256()
        sha256.update(f"{self.index}{self.prev_hash}{self.data}{self.valid_hash}{self.timestamp}".encode("utf-8"))
        return sha256.hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "prev_hash": self.prev_hash,
            "data": self.data,
            "valid_hash": self.valid_hash,
            "random_data": self.random_data,
            "timestamp": self.timestamp,
            "hash": self.hash,
            "attempts": self.attempts
        }

updated_memory_cost = 1500 # just initialize it

def write_difficulty_to_file(difficulty, filename='difficulty.txt'):
    with open(filename, 'w') as file:
        file.write(difficulty)

def update_memory_cost_periodically():
    global memory_cost
    global updated_memory_cost
    global gpu_mode
    time.sleep(2)
    while True:
        updated_memory_cost = fetch_difficulty_from_server()
        if updated_memory_cost != memory_cost:
            if gpu_mode:
                memory_cost = updated_memory_cost
                write_difficulty_to_file(updated_memory_cost)
            print(f"Updating difficulty to {updated_memory_cost}")
        time.sleep(5)

# Function to get difficulty level from the server
def fetch_difficulty_from_server():
    global memory_cost
    try:
        response = requests.get('http://xenminer.mooo.com/difficulty')
        response_data = response.json()
        return str(response_data['difficulty'])
    except Exception as e:
        print(f"An error occurred while fetching difficulty: {e}")
        return memory_cost  # Return last value if fetching fails

from tqdm import tqdm
import time

# ANSI escape codes
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"

normal_blocks_count = 0
super_blocks_count = 0
xuni_blocks_count = 0
def submit_block(key):
    global updated_memory_cost  # Make it global so that we can update it
    found_valid_hash = False

    global normal_blocks_count
    global super_blocks_count
    global xuni_blocks_count

    argon2_hasher = argon2.using(time_cost=difficulty, salt=b"XEN10082022XEN", memory_cost=updated_memory_cost, parallelism=cores, hash_len = 64)
    
    hashed_data = argon2_hasher.hash(key)
    isSuperblock = False
    for target in stored_targets:
        if target in hashed_data[-87:]:
        # Search for the pattern "XUNI" followed by a digit (0-9)
            if re.search("XUNI[0-9]", hashed_data) and is_within_five_minutes_of_hour():
                found_valid_hash = True
                break
            elif target == "XEN11":
                found_valid_hash = True
                capital_count = sum(1 for char in re.sub('[0-9]', '', hashed_data) if char.isupper())
                if capital_count >= 65:
                    isSuperblock = True
                    print(f"{RED}Superblock found{RESET}")
                break
            else:
                found_valid_hash = False
                break

    if found_valid_hash:
        print(f"\n{RED}Found valid hash for target {target}{RESET}")

        # Prepare the payload
        payload = {
            "hash_to_verify": hashed_data,
            "key": key,
            "worker": worker_id  # Adding worker information to the payload
            }

        print (payload)

        max_retries = 2
        retries = 0

        while retries <= max_retries:
            # Make the POST request
            response = requests.post(proxy, json=payload)
            # Print the HTTP status code
            print("HTTP Status Code:", response.status_code)
            if found_valid_hash and response.status_code == 200:
                if "XUNI" in hashed_data:
                    xuni_blocks_count += 1
                    break
                elif "XEN11" in hashed_data:
                    capital_count = sum(1 for char in re.sub('[0-9]', '', hashed_data) if char.isupper())
                    if capital_count >= 65:
                        super_blocks_count += 1
                    else:
                        normal_blocks_count += 1
            
            retries += 1
            print(f"Retrying... ({retries}/{max_retries})")
            time.sleep(5)  # You can adjust the sleep time


            # Print the server's response
            try:
                print("Server Response:", response.json())
            except Exception as e:
                print("An error occurred:", e)

    return key, hashed_data

def monitor_blocks_directory():
    global normal_blocks_count
    global super_blocks_count
    global xuni_blocks_count
    global memory_cost
    with tqdm(total=None, dynamic_ncols=True, desc=f"{GREEN}Mining{RESET}", unit=f" {GREEN}Blocks{RESET}") as pbar:
        pbar.update(0)
        while True:
            XENDIR = f"gpu_found_blocks_tmp/"
            if not os.path.exists(XENDIR):
                os.makedirs(XENDIR)
            for filename in os.listdir(XENDIR):
                filepath = os.path.join(XENDIR, filename)
                with open(filepath, 'r') as f:
                    data = f.read()
                submit_block(data)
                pbar.update(1)
                os.remove(filepath)
            superblock = f"{RED}super:{super_blocks_count}{RESET} "
            block = f"{GREEN}normal:{normal_blocks_count}{RESET} "
            xuni = f"{BLUE}xuni:{xuni_blocks_count}{RESET} "
            if(super_blocks_count == 0):
                superblock = ""
            if(normal_blocks_count == 0):
                block = ""
            if(xuni_blocks_count == 0):
                xuni = ""
            if super_blocks_count == 0 and normal_blocks_count == 0 and xuni_blocks_count == 0:
                pbar.set_postfix({"Details": f"Waiting for blocks..."}, refresh=True)
            else:
                pbar.set_postfix({"Details": f"{superblock}{block}{xuni}"}, refresh=True)

            time.sleep(1)  # Check every 1 seconds


if __name__ == "__main__":
    stored_targets = ['XEN11', 'XUNI']
    
    #Start difficulty monitoring thread
    difficulty_thread = threading.Thread(target=update_memory_cost_periodically)
    difficulty_thread.daemon = True  # This makes the thread exit when the main program exits
    difficulty_thread.start()
    if(gpu_mode):
        print(f"Using GPU mode")
        print('Make sure you are running ./xengpuminer at the same time')
        submit_thread = threading.Thread(target=monitor_blocks_directory)
        submit_thread.daemon = True  # This makes the thread exit when the main program exits
        submit_thread.start()
        try:
            while True:  # Loop forever
                time.sleep(10)  # Sleep for 10 seconds
        except KeyboardInterrupt:
            print("Main thread is finished")

