#!/usr/bin/python2.7
from pastebin import PastebinAPI, PastebinError
from datetime import datetime
import socket
import fcntl
import struct
import logging
import sys
import json

# Filenames
log_filename = '/home/pi/ipublish/ipublish.log'
urllog_filename = '/home/pi/ipublish/urls.log'
json_filename = '/home/pi/ipublish/params.json'
motion_log_filename = '/home/pi/motion.log'

# Log setup
logging.basicConfig(filename=log_filename, level=logging.DEBUG, format='%(asctime)s %(message)s')
logging.info('Started script.')

# Get json string
current_json_string = ''
try:
    logging.info('Opening file `' + json_filename + '`')
    with open(json_filename, 'r') as f:
        logging.info('Reading json file')
        current_json_string = f.read()
except:
    e = sys.exc_info()[0]
    logging.warning('Reading json file failed: ' + str(e))

# Parsing json
parsed_json = None
try:
    if current_json_string:
        logging.info('Parsing json')
        parsed_json = json.loads(current_json_string)
except:
    e = sys.exc_info()[0]
    logging.warning('Parsing json failed: ' + str(e))
    logging.warning('Exiting')
    exit()

# Check if json values exist
dev_key = ''
my_key = ''
motion_line_number = None
got_motion_line_number = False
if parsed_json.has_key('dev_key'):
    dev_key = parsed_json['dev_key']
    logging.info('dev_key = ' + dev_key)
else:
    logging.warning('dev_key does not exist in json. Exiting.')
    exit()
if parsed_json.has_key('my_key'):
    my_key = parsed_json['my_key']
    logging.info('my_key = ' + my_key)
else:
    logging.warning('my_key does not exist in json. Exiting.')
    exit()
if parsed_json.has_key('motion_line_number'):
    motion_line_number = parsed_json['motion_line_number']
    got_motion_line_number = True
    logging.info('motion_line_number = ' + str(motion_line_number))
else:
    logging.warning('motion_line_number does not exist in json. Exiting.')
    exit()

# Grabbing motion log string
motion_log_string = ''
num_new_log_lines = 0
if got_motion_line_number:
    logging.info('Got motion line number, starting to read motion log')
    logging.info('Opening motion log file: ' + motion_log_filename)
    try:
        with open(motion_log_filename, 'r') as f:
            logging.info('Opened motion log file')
            num_motion_log_lines = 0
            logging.info('Looping through log lines')
            for i, line in enumerate(f):
                num_motion_log_lines += 1
                if i >= motion_line_number:
                    motion_log_string += line
                    num_new_log_lines += 1
        motion_log_string = motion_log_string.rstrip()
        logging.info('Looped through log lines. Current line number: ' + str(num_motion_log_lines))
        motion_line_number = num_motion_log_lines
    except:
        e = sys.exc_info()[0]
        logging.warning('Error while opening file or looping through: ' + str(e))

# Create get ip function
def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip_address_str = socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,
        struct.pack('256s', ifname[:15])
    )[20:24])
    return ip_address_str

# Filter log string
logging.info('Filtering log string.')
filtered_log_string = ''
num_filtered_lines = 0
for line in motion_log_string.splitlines():
    if '[EVT]' in line:
        filtered_log_string += line + '\n'
        num_filtered_lines += 1
filtered_log_string = filtered_log_string.strip()
logging.info('Filtered log string to ' + str(num_filtered_lines) + ' lines.')
try:
    with open('/home/pi/ipublish/test.log', 'a') as f:
        logging.info('Writing filtered log string to test log.')
        f.write(filtered_log_string + '\n')
except:
    e = sys.exc_info()[0]
    logging.warning('Unknown error ' + str(e))

# Get time
now = datetime.now()
now_str = str(now)[:19]
logging.info('Got current time: ' + now_str + '.')

# Get IP
ip_str = ''
try:
    ip_str = get_ip_address('eth0')
    logging.info('Got IP address: ' + ip_str + '.')
except:
    e = sys.exc_info()[0]
    logging.warning('Failed when trying to retrieve IP address: ' + str(e))
    ip_str = 'No IP, failed when trying to retrieve it'

# Create paste string
paste_name = 'RPI IP at ' + now_str
paste_string = ip_str

if motion_log_string:
    logging.info('Appending ' + str(num_new_log_lines) + ' log lines to paste string.')
    paste_string = ip_str + '\n\nMotion event log:\n\n' + motion_log_string
else:
    logging.info('No log lines appended to paste string.')
    paste_string = ip_str + '\n\nNo new log info.'

# Create pastebin object
pb = PastebinAPI()
logging.info('Created PastebinAPI object.')

# Paste it
logging.info('Trying to upload to pastebin with name `' + paste_name + '` and message `' + ip_str + '` plus ' + str(num_new_log_lines) + ' motion log lines.')
pburl = ''
paste_successful = False
try:
    pburl = pb.paste(dev_key, paste_string, my_key, paste_name, None, 'unlisted', '1D')
    logging.info('Successful pastebin url: ' + pburl)
    paste_successful = True
except PastebinError as e:
    logging.info('Got a pastebin error, checking if it is an http vs https issue.')
    if e.message.startswith('https://pastebin.com/'):
        pburl = e.message
        logging.info('Message starts with `https://pastebin.com/` so it is assumed to not be an actual error. Url: ' + pburl)
        paste_successful = True
    else:
        logging.warning('Got a real pastebin error: ' + str(e))
except:
    e = sys.exc_info()[0]
    logging.warning('Unknown error: ' + str(e))
    logging.warning('Error message: ' + str(e.message))

# Append url to url log
if pburl:
    logging.info('Got a pastebin url. Writing to url log.')
    logstr = now_str + '\t' + pburl
    try:
        with open(urllog_filename, 'a') as f:
            logging.info('Opened url log `' + urllog_filename + '`')
            f.write(logstr + '\n')
            logging.info('Appended `' + logstr + '`')
    except:
        e = sys.exc_info()[0]
        logging.warning('Writing to `' + urllog_filename + '` failed: ' + str(e))
else:
    logging.warning('No pb url, no writing.')

# Updating json
if paste_successful:
    parsed_json['motion_line_number'] = motion_line_number
    logging.info('Updating json')
    try:
        with open(json_filename, 'w') as f:
            json_string = json.dumps(parsed_json)
            logging.info('Created json string `' + json_string + '`')
            f.write(json_string + '\n')
            logging.info('Wrote to json file')
    except:
        e = sys.exc_info()[0]
        logging.warning('Error while writing to json file: ' + str(e))
else:
    logging.warning('As the paste was unsuccessful, we are not updating the json')

logging.info('Ended script.')

