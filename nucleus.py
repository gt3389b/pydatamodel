"""
Copyright (c) 2016 John Blackford

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

# File Name: nucleus.py
#
# Description: Rudimentary Agent Database
#
# Functionality:
#  - Dictionary as a database (key=full parameter path, value=parameter value)
#  - The database is initialized from a JSON formatted file
#  - Get command for full parameter path
#  - Update command for full parameter path
#  - Insert command for tables
#  - Delete command for tables
#  - Find commands for wild-carded or partial parameter paths (returns full parameter paths)
#  --- find_params: find parameter paths
#  --- find_instances: find multi-object instance partial paths
#  --- find_impl_objects: find implemented object partial paths
#  - Save command (saves the contents of the database back to a file)
#
"""

import re
import json
import os
import time
import logging
import datetime
#import prometheus_client
import requests
from dotenv import load_dotenv
import operator
import functools
from collections import defaultdict
import datetime
import pprint
from cachier import cachier
import datetime


load_dotenv()

from flask import Flask, render_template

app = Flask(__name__)


# pylint: disable-msg=no-value-for-parameter
"""
DB_GET_SUMMARY_METRIC = \
    prometheus_client.Summary("database_get_processing_seconds",
                              "Time spent handling Database Get Call")
# pylint: disable-msg=no-value-for-parameter
DB_UPDATE_SUMMARY_METRIC = \
    prometheus_client.Summary("database_update_processing_seconds",
                              "Time spent handling Database Update Call")
# pylint: disable-msg=no-value-for-parameter
DB_INSERT_SUMMARY_METRIC = \
    prometheus_client.Summary("database_insert_processing_seconds",
                              "Time spent handling Database Insert Call")
# pylint: disable-msg=no-value-for-parameter
DB_DELETE_SUMMARY_METRIC = \
    prometheus_client.Summary("database_delete_processing_seconds",
                              "Time spent handling Database Delete Call")
# pylint: disable-msg=no-value-for-parameter
DB_FIND_PARAMS_SUMMARY_METRIC = \
    prometheus_client.Summary("database_find_params_processing_seconds",
                              "Time spent handling Database FindParams Call")
# pylint: disable-msg=no-value-for-parameter
DB_FIND_INSTANCES_SUMMARY_METRIC = \
    prometheus_client.Summary("database_find_instances_processing_seconds",
                              "Time spent handling Database FindInstances Call")
# pylint: disable-msg=no-value-for-parameter
DB_FIND_OBJECTS_SUMMARY_METRIC = \
    prometheus_client.Summary("database_find_objects_processing_seconds",
                              "Time spent handling Database FindObjects Call")
# pylint: disable-msg=no-value-for-parameter
DB_FIND_IMPL_OBJECTS_SUMMARY_METRIC = \
    prometheus_client.Summary("database_find_impl_objects_processing_seconds",
                              "Time spent handling Database FindImplObjects Call")
"""


class Database:

    """Represents a simple database"""
    def __init__(self, dm_filename, base_url, creds, debug=False):
        """Initialize the DB from a file"""
        self._start_time = time.time()
        self._base_url = base_url
        self._creds = creds
        self._db = {}

        if debug:
            logging.basicConfig(level=logging.DEBUG)
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.debug("Initializing the Database...")

        # Retrieve the Implemented Data Model
        with open(dm_filename, "r") as dm_in_json:
            try:
                self._dm = json.load(dm_in_json)
            except ValueError as parse_err:
                self._dm = {}
                self._log.error("Implemented Data Model is NOT properly formatted JSON: %s", parse_err)

        #Load DB
        self.reset()

    def _process_webpa_resp(self, webpa_parameters):
        result = {}

        for parameter in webpa_parameters:
            if parameter['parameterCount'] > 1:
                for entry in parameter['value']:
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
                if parameter['dataType'] == 2:
                    #print("%s:%d" % (entry['name'], int(entry['value'])))
                    result[parameter['name']]= int(parameter['value'])
                else:
                    if parameter['value'] == "":
                        result[parameter['name']]= ""
                    else:
                        #print("%s:%s" % (entry['name'], entry['value']))
                        result[parameter['name']]= parameter['value']
        return result

    def _get_webpa(self, mac, paths):
       r = requests.get(self._base_url +"mac:"+ mac +"/config?names="+ paths, headers={'Authorization':'Basic '+self._creds})
       #print(name, r.text)
       if r.status_code == 200:
          return self._process_webpa_resp(r.json()['parameters'])
       elif r.status_code == 520:
          print(r.status_code, r.text, paths)
          return []
       else:
          print(r.status_code, r.text, paths)
          return None

    #@DB_GET_SUMMARY_METRIC.time()
    def get(self, mac, paths):
        """Retrieve the value of the incoming path, or throw a NoSuchPathError"""
        value = None

        value = self._get_webpa(mac, paths)

        # when there are multiple paths, the server doesn't tell you which one failed
        if value == None:
            raise NoSuchPathError(paths)

        """
        if paths in self._db:
            value = self._db[path]
        else:
            value = self._get_webpa(mac, path)

            if value == None:
                raise NoSuchPathError(path)
        """

        return value

    def _generic_dm_path(self, path):
        """Turn a DM Path into a Generic one by replacing instance numbers and wildcards"""
        generic_path = re.sub(r'\.[0-9]+\.', r'.{i}.', path)  # Instance Number Addressing
        generic_path = re.sub(r'\.\*\.', r'.{i}.', generic_path)  # Wild-card Searching

        return generic_path

    def _update(self, path, value):
        dm_param_path = self._generic_dm_path(path)

        # Validate that path is in the Implemented Data Model
        if dm_param_path in self._dm:
            self._db[path] = value
            #self._save()
        else:
            raise NoSuchPathError(path)

    #@DB_UPDATE_SUMMARY_METRIC.time()
    def update(self, path, value):
        """Change the value of the incoming path, or throw a NoSuchPathError"""
        if self.is_param_writable(path):
            self._update(path, value)
        else:
            raise NoSuchPathError(path)

    def version(self):
        return "1.0"

    def is_param_writable(self, param_path):
        """Validate whether the supplied parameter path is readWrite (return True)"""
        is_writable = False
        dm_param_path = self._generic_dm_path(param_path)

        # Validate that path is in the Implemented Data Model
        if dm_param_path in self._dm:
            if self._dm[dm_param_path] == "readWrite":
                is_writable = True
        else:
            raise NoSuchPathError(dm_param_path)

        return is_writable

    def reset(self):
        # Retrieve Gravity values
        pass

class NoSuchPathError(Exception):
    """A Database NoSuchPath Error"""
    def __init__(self, value):
        """Initialize the Exception"""
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        """Return the String value of the Exception"""
        return repr(self.value)

class NucleusDevice(object):
    def __init__(self, base_url, creds, mac):
        self._mac = mac
        self._db = Database("erdk-dm.json", base_url, creds, None)

    def get(self):
        def dd_to_dict(d):
            if isinstance(d, defaultdict):
                d = {k: dd_to_dict(v) for k, v in d.items()}
            return d

        def get_path(paths, master_dict):

            query_result = self._db.get(self._mac, paths)

            for entry in query_result:
                keys = entry.split('.')
                lastplace = functools.reduce(operator.getitem, keys[:-1], master_dict)
                lastplace[keys[-1]] = query_result[entry]
            return master_dict

        dict_result = {}

        infinitedict = lambda: defaultdict(infinitedict)
        dict_result = infinitedict()

        """
        for path in ['Device.DeviceInfo.X_COMCAST-COM_CM_MAC', 
                'Device.DeviceInfo.X_CISCO_COM_BootloaderVersion',
                'Device.DeviceInfo.X_CISCO_COM_FirmwareName',
                'Device.DeviceInfo.X_CISCO_COM_FirmwareBuildTime',
                'Device.DeviceInfo.Hardware',
                'Device.DeviceInfo.Manufacturer',
                'Device.DeviceInfo.ModelName',
                'Device.DeviceInfo.Description',
                'Device.DeviceInfo.ProductClass',
                'Device.DeviceInfo.SerialNumber',
                'Device.DeviceInfo.HardwareVersion',
                'Device.DeviceInfo.SoftwareVersion',
                'Device.DeviceInfo.UpTime',
                'Device.Bridging.Bridge.',
                'Device.Ethernet.',
                'Device.WiFi.',
                'Device.Hosts.',
                #'Device.DeviceInfo.X_RDKCENTRAL-COM_xOpsDeviceMgmt.Mesh.',
                #"Device.WiFi.AccessPoint."]:
                ]:
            dict_result = get_path(path, dict_result)
        """
        #paths = ','.join(['Device.DeviceInfo.X_COMCAST-COM_CM_MAC','Device.DeviceInfo.X_CISCO_COM_BootloaderVersion'])
        paths =','.join(['Device.DeviceInfo.X_COMCAST-COM_CM_MAC', 
                'Device.DeviceInfo.X_CISCO_COM_BootloaderVersion',
                'Device.DeviceInfo.X_CISCO_COM_FirmwareName',
                'Device.DeviceInfo.X_CISCO_COM_FirmwareBuildTime',
                'Device.DeviceInfo.Hardware',
                'Device.DeviceInfo.Manufacturer',
                'Device.DeviceInfo.ModelName',
                'Device.DeviceInfo.Description',
                'Device.DeviceInfo.ProductClass',
                'Device.DeviceInfo.SerialNumber',
                'Device.DeviceInfo.HardwareVersion',
                'Device.DeviceInfo.SoftwareVersion',
                'Device.DeviceInfo.UpTime',
                'Device.Bridging.Bridge.',
                'Device.Ethernet.',
                'Device.WiFi.',
                'Device.Hosts.'])

        dict_result = get_path(paths, dict_result)

        return str(json.dumps(dd_to_dict(dict_result)))

    def __repr__(self):
        return 'device_'+self._mac

@cachier(stale_after=datetime.timedelta(seconds=10))
def get_device_twin(base_url, creds, mac):
    nd = NucleusDevice(base_url, creds, mac)
    return nd.get()

@app.route('/device/<mac>')
def get_device_info(mac):
    creds = os.getenv("TOKEN")
    base_url = os.getenv("BASE_URL")
    try:
        get_device_twin.clear_cache()
        result = get_device_twin(base_url, creds, mac)
    except:
        return {'message':'ERROR:  Device does not exist'}
    return result

def main():
    creds = os.getenv("TOKEN")
    base_url = os.getenv("BASE_URL")
    mac="B827EB5DF064"
    mac="b827eba77b12"
    mac="b827eb112233"
    #mac="000000000001"

    get_device_twin.clear_cache()
    print(get_device_twin(base_url, creds, mac))

if __name__ == "__main__":
    app.run()
    #main()
