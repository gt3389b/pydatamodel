import re
import json
import time
import logging
import datetime
import threading
import pprint
import utils

result_file = "results.json"

result = {}

# Retrieve the Implemented Data Model
with open(result_file, "r") as result_in_json:
    try:
        _dm = json.load(result_in_json)['parameters'][0]
        #print(_dm)
        #print(_dm['name'])
        for entry in _dm['value']:
            if entry['dataType'] == 2:
                #print("%s:%d" % (entry['name'], int(entry['value'])))
                result[entry['name']]= int(entry['value'])
            else:
                if entry['value'] == "":
                    #print("%s:\"\"" % (entry['name']))
                    result[entry['name']]= ""
                else:
                    #print("%s:%s" % (entry['name'], entry['value']))
                    result[entry['name']]= entry['value']
    except ValueError as parse_err:
        _dm = {}

with open('erdk-db.json', 'w') as outfile:
    json.dump(result, outfile)
