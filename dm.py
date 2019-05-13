import json
import re
import json
import time
import logging
import datetime
import threading

import pprint

class DataType:
    def __init__(self):
        self._name = None
        self._type = None
        self._description = None
        self._base = None

    def from_dict(self, type_dict):
        for key in type_dict:
            if '@name' == key:
                self._name = type_dict['@name']
            elif '@base' == key:
                self._base = type_dict['@base']
            elif 'string' == key:
                self._type = 'string'
            elif 'unsignedLong' == key:
                self._type = 'unsignedLong'
            elif 'unsignedInt' == key:
                self._type = 'unsignedInt'
            elif 'int' == key:
                self._type = 'int'
            elif 'size' == key:
                self._type = 'size'
            elif 'list' == key:
                self._type = 'list'
            elif 'description' == key:
                self._description = type_dict['description']
            else:
                print("UNKNOWN KEY:  "+key+"  VALUE: "+type_dict[key])

    def __str__(self):
        return "name: "+str(self._name)+" type:"+str(self._type)


class Model(object):
    def __init__(self):
        self._path = None
        self._type = None
        self._description = None
        self._access = None
        self._maxEntries = None
        self._minEntries = None
        self._version = None
        self._numEntriesParameter = None

        self._uniqueKeys = {}
        self._parameter = {}
        self._event = {}
        self._command = {}

    def from_dict(self, model_dict):
        for key in model_dict:
            if '@name' == key:
                self._path = model_dict['@name']
            elif '@access' == key:
                self._access = model_dict['@access']
            elif 'uniqueKey' == key:
                pass
            elif '@noUniqueKeys' == key:
                pass
            elif '@fixedObject' == key:
                self._fixedObject = True
            elif 'parameter' == key:
                pass
            elif 'command' == key:
                pass
            elif 'event' == key:
                pass
            elif 'description' == key:
                self._description = model_dict['description']
            elif '@maxEntries' == key:
                self._maxEntries = model_dict['@maxEntries']
            elif '@minEntries' == key:
                self._minEntries = model_dict['@minEntries']
            elif '@version' == key:
                self._version = model_dict['@version']
            elif '@mountPoint' == key:
                self._mountPoint = model_dict['@mountPoint']
            elif '@mountType' == key:
                self._mountType = model_dict['@mountType']
            elif '@enableParameter' == key:
                self._enableParameter = model_dict['@enableParameter']
            elif '@numEntriesParameter' == key:
                self._numEntriesParameter = model_dict['@numEntriesParameter']
            else:
                print("UNKNOWN KEY:  "+key+"  VALUE: "+str(model_dict[key]))

    def __str__(self):
        return "path: "+str(self._path)+" access:"+str(self._access)

    def __repr__(self):
        return self.__dict__

class DataModel(object):
    """Represents a datamodel"""
    def __init__(self, dm_filename, debug=False):
        """Initialize the DB from a file"""
        self._file_write_lock = threading.Lock()
        self._new_inst_num_lock = threading.Lock()
        self._start_time = time.time()

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

        self.parseJson()

    def parseParams(self, params):
        items = {}
        #pprint.pprint(params)
        if isinstance(params, list):
            for param in params:
                if '@name' in param:
                    #pprint.pprint(param)
                    items['name'] = param['@name']
                    items['access'] = param['@access']
        else:
            if '@name' in params:
                #pprint.pprint(param)
                items['name'] = params['@name']
                items['access'] = params['@access']
        return items

    def parseJson(self):
        self._model = {}
        for dtype in self._dm['document']['dataType']:
            d = DataType()
            d.from_dict(dtype)

        for model in self._dm['document']['model']['object']:
            #m = Model()
            #m.from_dict(model)
            data = {}
            for key in model:
                if '@name' == key:
                    #data['path'] = model['@name']
                    pass
                elif '@access' == key:
                    data['access'] = model['@access']
                elif 'uniqueKey' == key:
                    pass
                elif '@noUniqueKeys' == key:
                    pass
                elif '@fixedObject' == key:
                    data['fixedObject'] = True
                elif 'parameter' == key:
                    data['parameter'] = self.parseParams(model['parameter'])
                elif 'command' == key:
                    pass
                elif 'event' == key:
                    pass
                elif 'description' == key:
                    #data['description'] = model['description']
                    pass
                elif '@maxEntries' == key:
                    data['maxEntries'] = model['@maxEntries']
                elif '@minEntries' == key:
                    data['minEntries'] = model['@minEntries']
                elif '@version' == key:
                    data['version'] = model['@version']
                elif '@mountPoint' == key:
                    data['mountPoint'] = model['@mountPoint']
                elif '@mountType' == key:
                    data['mountType'] = model['@mountType']
                elif '@enableParameter' == key:
                    data['enableParameter'] = model['@enableParameter']
                elif '@numEntriesParameter' == key:
                    data['numEntriesParameter'] = model['@numEntriesParameter']
                else:
                    print("UNKNOWN KEY:  "+key+"  VALUE: "+str(model[key]))
            self._model[model['@name']] = data 

    def find_path_attrs(self, partial_path):
        if partial_path.endswith("."):
            # Turn the incoming path into a regex to validate it is in the implemented data model
            dm_regex_str = self._dm_regex(partial_path, True)
            print(dm_regex_str)
        print(self._generic_dm_path(partial_path))

    def _dm_regex(self, path, partial_path):
        """Generate a regex for determining whether or not a path is in the DM"""
        dm_regex_str = "^" + path  # Starts with
        dm_regex_str = re.sub(r'\.[0-9]+\.', r'.{i}.', dm_regex_str)  # Instance Number Addressing
        dm_regex_str = re.sub(r'\.\*\.', r'.{i}.', dm_regex_str)  # Wild-card Searching
        dm_regex_str = re.sub(r'\.', r'\.', dm_regex_str)  # Replace '.' with explicit '.' search

        if partial_path:
            dm_regex_str = dm_regex_str + ".*"

        return dm_regex_str

    def _generic_dm_path(self, path):
        """Turn a DM Path into a Generic one by replacing instance numbers and wildcards"""
        generic_path = re.sub(r'\.[0-9]+\.', r'.{i}.', path)  # Instance Number Addressing
        generic_path = re.sub(r'\.\*\.', r'.{i}.', generic_path)  # Wild-card Searching

    def _strip_path(self, path):
        obj_path = re.sub(r'\.*\.([^\.]*)$', r'.', path)
        param = re.findall(r'\.*\.([^\.]*)$', path)
        return (obj_path, param[0])

def main():
    dm = DataModel("dm.json", True)
    #dm.find_path_attrs('Device.')
    #dm.find_path_attrs('Device.2.test2')
    #dm.find_path_attrs('Device.2.')
    #dm.find_path_attrs('Device.{i}.test2')
    #print(re.sub(r'\.*\.([^\.]*)$', "Device."))
    print(dm._strip_path("Device.Russell.{i}.Test"))
    print(dm._strip_path("Device.Russell.{i}."))
    print(dm._strip_path("Device.Russell.Test2"))

if __name__ == "__main__":
    main()
