import json
import requests
import pprint
from dotenv import load_dotenv
import operator
import functools
from collections import defaultdict
load_dotenv()

# OR, the same with increased verbosity
load_dotenv(verbose=True)

# settings.py
import os
TOKEN = os.getenv("TOKEN")
BASE_URL = os.getenv("BASE_URL")

print(TOKEN)

def process_webpa_resp(_dm):
    result = {}

    if _dm['parameterCount'] > 1:
        for entry in _dm['value']:
            if entry['dataType'] == 2:
                #print("%s:%d" % (entry['name'], int(entry['value'])))
                result[entry['name']]= int(entry['value'])
            else:
                if entry['value'] == "":
                    result[entry['name']]= ""
                else:
                    #print("%s:%s" % (entry['name'], entry['value']))
                    result[entry['name']]= entry['value']
    else:
        if _dm['dataType'] == 2:
            #print("%s:%d" % (entry['name'], int(entry['value'])))
            result[_dm['name']]= int(_dm['value'])
        else:
            if _dm['value'] == "":
                result[_dm['name']]= ""
            else:
                #print("%s:%s" % (entry['name'], entry['value']))
                result[_dm['name']]= _dm['value']
    return result

mac="B827EB5DF064"

output_data = {}

filepath = 'query.txt'
with open(filepath) as fp:
   name = fp.readline()
   cnt = 1
   while name:
       r = requests.get(BASE_URL+"mac:"+mac+"/config?names="+name.strip(), headers={'Authorization':'Basic '+TOKEN})
       #print(name, r.text)
       response_json = r.json()['parameters'][0]
       result = process_webpa_resp(response_json)
       output_data.update(result)
       name = fp.readline()

def dd_to_dict(d):
    if isinstance(d, defaultdict):
        d = {k: dd_to_dict(v) for k, v in d.items()}
    return d

infinitedict = lambda: defaultdict(infinitedict)
wf = infinitedict()

for entry in output_data:
    keys = entry.split('.')
    lastplace = functools.reduce(operator.getitem, keys[:-1], wf)
    lastplace[keys[-1]] = output_data[entry]

pprint.pprint(dd_to_dict(wf))
