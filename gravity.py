import re
import json
import time
import logging
import datetime
import threading
import pprint
import utils
import operator
import functools
from collections import defaultdict

class Database:
    """Represents a simple database"""
    def __init__(self, dm_filename, db_filename, net_intf, debug=False):
        """Initialize the DB from a file"""
        self._net_intf = net_intf
        self._db_filename = db_filename
        self._file_write_lock = threading.Lock()
        self._new_inst_num_lock = threading.Lock()
        self._start_time = time.time()

        self._supported_insert_path_list = [
            "Device.Services.HomeAutomation.{i}.Camera.{i}.Pic.",
            "Device.Test."
        ]
        self._supported_delete_path_list = [
            "Device.Services.HomeAutomation.{i}.Camera.{i}.Pic.{i}.",
            "Device.Test."
        ]

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

    def __repr__(self):
        def dd_to_dict(d):
            if isinstance(d, defaultdict):
                d = {k: dd_to_dict(v) for k, v in d.items()}
            return d

        result = {}

        infinitedict = lambda: defaultdict(infinitedict)
        result = infinitedict()

        for entry in self._db:
            keys = entry.split('.')
            lastplace = functools.reduce(operator.getitem, keys[:-1], result)
            lastplace[keys[-1]] = self._db[entry]
        return str(json.dumps(dd_to_dict(result)))


    #@DB_GET_SUMMARY_METRIC.time()
    def get(self, path):
        """Retrieve the value of the incoming path, or throw a NoSuchPathError"""
        value = None

        if path in self._db:
            if self._db[path] == "__UPTIME__":
                value = int(time.time() - self._start_time)
            elif self._db[path] == "__IPADDR__":
                value = utils.IPAddr.get_ip_addr(self._net_intf)
            elif self._db[path] == "__CURR_TIME__":
                time_zone = self._db["Device.Time.LocalTimeZone"]
                tz_part = time_zone.split(",")[0]
                now = datetime.datetime.now()
                now_str = now.strftime("%Y-%m-%dT%H:%M:%S")
                if tz_part == "CST6CDT":
                    now_str += "-06:00"
                else:
                    now_str += "Z"
                value = now_str
            elif self._db[path] == "__NUM_ENTRIES__":
                inst_path = re.sub(r'NumberOfEntries', '.', path)
                found_instances = self.find_instances(inst_path)
                value = len(found_instances)
            else:
                value = self._db[path]
        elif path.endswith('.'):
            value = self.get_obj(path)
        else:
            raise NoSuchPathError(path)

        return value

    def get_obj(self, partial_path):
        results = {}
        items = self.find_params(partial_path)
        for item in items:
            results[item] = self.get(item)
        return results

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

    #@DB_FIND_PARAMS_SUMMARY_METRIC.time()
    def find_params(self, path):
        """Retrieve a set of parameter paths that match the incoming path"""
        found_keys = []
        is_implemented_path = False

        # Turn the incoming path into a regex to validate it is in the implemented data model
        dm_regex_str = self._dm_regex(path, path.endswith("."))
        self._log.debug("find_params: Using regex \"%s\" to validate Path [%s] is in the Implemented Data Model",
                     dm_regex_str, path)

        # Turn the incoming path into a regex to get the matching paths
        db_regex_str = self._db_regex(path, path.endswith("."))
        self._log.debug("find_params: Using regex \"%s\" to retrieve values from the Database for Path [%s]",
                     db_regex_str, path)

        # Validate that path is in the Implemented Data Model
        dm_keys = self._dm.keys()
        for dm_key in dm_keys:
            if re.fullmatch(dm_regex_str, dm_key) is not None:
                is_implemented_path = True
                break

        # If the path is Valid then retrieve the matching paths
        if is_implemented_path:
            for param_path in self._db:
                if re.fullmatch(db_regex_str, param_path) is not None:
                    path_parts = param_path.split(".")
                    path_part_len = len(path_parts) - 1

                    if not self._is_meta_parameter(path_parts, path_part_len):
                        found_keys.append(param_path)
        else:
            raise NoSuchPathError(path)

        return found_keys
    
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

    #@DB_FIND_INSTANCES_SUMMARY_METRIC.time()
    def find_instances(self, partial_path):
        """Retrieve a set of object instance paths that match the incoming path"""
        found_keys = []
        is_implemented_path = False

        if partial_path.endswith("."):
            # Turn the incoming path into a regex to validate it is in the implemented data model
            dm_regex_str = self._dm_regex(partial_path, True)
            self._log.debug("find_instances: Using regex \"%s\" to validate Path [%s] is in the Implemented Data Model",
                         dm_regex_str, partial_path)

            # Turn the incoming path into a regex to get the matching paths
            db_regex_str = self._db_regex(partial_path, True)
            self._log.debug("find_instances: Using regex \"%s\" to retrieve values from the Database for Path [%s]",
                         db_regex_str, partial_path)
        else:
            raise NoSuchPathError(partial_path)

        # length minus 1 due to the ending "." causing 1 more split
        partial_path_part_len = len(partial_path.split(".")) - 1

        # Validate that path is in the Implemented Data Model
        for dm_key in self._dm:
            if re.fullmatch(dm_regex_str, dm_key) is not None:
                # Validate that the partial_path is a multi-instance object
                dm_key_parts = dm_key.split(".")
                if dm_key_parts[partial_path_part_len] == "{i}":
                    is_implemented_path = True
                    break

        # If the path is Valid then retrieve the matching paths
        if is_implemented_path:
            for path in self._db:
                if re.fullmatch(db_regex_str, path) is not None:
                    # We only want the path to the next level (instance identifiers)
                    path_parts = path.split(".")
                    built_path = utils.PathHelper.build_path_from_parts(path_parts, partial_path_part_len)
                    found_key = built_path + path_parts[partial_path_part_len] + "."

                    if not self._is_meta_parameter(path_parts, partial_path_part_len):
                        # Only add it to found_keys if we haven't done so already
                        if found_key not in found_keys:
                            found_keys.append(found_key)
        else:
            raise NoSuchPathError(partial_path)

        return found_keys

    #@DB_FIND_OBJECTS_SUMMARY_METRIC.time()
    def find_objects(self, partial_path):
        """Retrieve a set of instantiated object paths that match the incoming path"""
        found_keys = []
        is_implemented_path = False

        if partial_path.endswith("."):
            # Turn the incoming path into a regex to validate it is in the implemented data model
            dm_regex_str = self._dm_regex(partial_path, True)
            self._log.debug("find_objects: Using regex \"%s\" to validate Path [%s] is in the Implemented Data Model",
                         dm_regex_str, partial_path)

            # Turn the incoming path into a regex to get the matching paths
            db_regex_str = self._db_regex(partial_path, True)
            self._log.debug("find_objects: Using regex \"%s\" to retrieve values from the Database for Path [%s]",
                         db_regex_str, partial_path)
        else:
            raise NoSuchPathError(partial_path)

        # length minus 1 due to the ending "." causing 1 more split
        partial_path_part_len = len(partial_path.split(".")) - 1

        # Validate that path is in the Implemented Data Model
        for dm_key in self._dm:
            if re.fullmatch(dm_regex_str, dm_key) is not None:
                is_implemented_path = True
                break

        # If the path is Valid then retrieve the matching paths
        if is_implemented_path:
            for path in self._db:
                if re.fullmatch(db_regex_str, path) is not None:
                    # We only want the path to the next level (instance identifiers)
                    path_parts = path.split(".")
                    found_key = utils.PathHelper.build_path_from_parts(path_parts, partial_path_part_len)

                    if found_key not in found_keys:
                        found_keys.append(found_key)
        else:
            raise NoSuchPathError(partial_path)

        return found_keys

    #@DB_FIND_IMPL_OBJECTS_SUMMARY_METRIC.time()
    def find_impl_objects(self, partial_path, next_level):
        """Retrieve a set of implemented object paths that match the incoming path"""
        found_keys = []
        is_implemented_path = False
        generic_partial_path = self._generic_dm_path(partial_path)

        if partial_path.endswith("."):
            # Turn the incoming path into a regex to validate it is in the implemented data model
            dm_regex_str = self._dm_regex(partial_path, True)
            self._log.debug(
                "find_impl_objects: Using regex \"%s\" to validate Path [%s] is in the Implemented Data Model",
                dm_regex_str, partial_path)
        else:
            raise NoSuchPathError(partial_path)

        # length minus 1 due to the ending "." causing 1 more split
        partial_path_part_len = len(partial_path.split(".")) - 1

        # Validate that path is in the Implemented Data Model
        for dm_key in self._dm:
            if re.fullmatch(dm_regex_str, dm_key) is not None:
                self._log.debug("find_impl_objects: Found full match: %s", dm_key)
                found_key = None
                key_parts = dm_key.split(".")
                key_parts_len = len(key_parts)
                is_implemented_path = True

                if next_level:
                    if key_parts_len > partial_path_part_len + 1:
                        built_path = utils.PathHelper.build_path_from_parts(key_parts, partial_path_part_len)
                        found_key = built_path + key_parts[partial_path_part_len] + "."
                    else:
                        print(key_parts)
                        self._log.debug("find_impl_objects: key parts [%s] less than/equal partial path parts [%s]",
                                     str(key_parts_len), str(partial_path_part_len + 1))
                else:
                    inx = 0
                    found_key = ""
                    while inx < (key_parts_len - 1):
                        found_key += key_parts[inx]
                        found_key += "."
                        inx += 1

                # Only add it to found_keys if we haven't done so already
                if found_key is not None:
                    self._log.debug("find_impl_objects: Found key: %s", found_key)
                    if found_key not in found_keys:
                        self._log.debug("find_impl_objects: Found key [%s] not already in the list", found_key)
                        # Don't add the incoming partial_path
                        if not found_key == generic_partial_path:
                            self._log.debug("find_impl_objects: Adding found key [%s] to the list", found_key)
                            found_keys.append(found_key)

        # If the path is Valid then retrieve the matching paths
        if not is_implemented_path:
            raise NoSuchPathError(partial_path)

        return found_keys

    #@DB_INSERT_SUMMARY_METRIC.time()
    def insert(self, partial_path):
        """Insert a new record in the table"""

        # Check to see if the returned list is not empty
        self._log.debug("insert: find %s", partial_path)
        if self.find_impl_objects(partial_path, True):
            dm_regex_str = partial_path
            dm_regex_str = re.sub(r'\{(.+?)\}', '{i}', dm_regex_str)
            dm_regex_str = re.sub(r'\.\d+\.', '.{i}.', dm_regex_str)
            self._log.debug("insert: Using regex \"%s\" to validate Path [%s] is in the Supported Insert Path List",
                         dm_regex_str, partial_path)

            if dm_regex_str in self._supported_insert_path_list:
                #next_inst_num_path = partial_path + "__NextInstNum__"
                next_inst_num_path = partial_path[:-1] + "NumberOfEntries"
                print(next_inst_num_path)
                with self._new_inst_num_lock:
                    try:
                        next_inst_num = self.get(next_inst_num_path) + 1
                    except NoSuchPathError:
                        next_inst_num = 1
                    self._update(next_inst_num_path, next_inst_num)
                    self._save()

                """
                if dm_regex_str == "Device.Services.HomeAutomation.{i}.Camera.{i}.Pic.":
                    self._db[partial_path + str(next_inst_num) + ".URL"] = ""
                    self._save()
                else:
                    raise NotImplementedError()
                """
            else:
                raise NoSuchPathError(partial_path)
        else:
            raise NoSuchPathError(partial_path)

        return next_inst_num

    #@DB_DELETE_SUMMARY_METRIC.time()
    def delete(self, partial_path):
        """Remove an existing record from the table"""

        # Check to see if the returned list is not empty
        if self.find_objects(partial_path):
            dm_regex_str = partial_path
            dm_regex_str = re.sub(r'\{(.+?)\}', '{i}', dm_regex_str)
            dm_regex_str = re.sub(r'\.\d+\.', '.{i}.', dm_regex_str)
            self._log.debug("delete: Using regex \"%s\" to validate Path [%s] is in the Supported Delete Path List",
                         dm_regex_str, partial_path)

            if dm_regex_str in self._supported_delete_path_list:
                if dm_regex_str == "Device.Services.HomeAutomation.{i}.Camera.{i}.Pic.{i}.":
                    del self._db[partial_path + "URL"]
                    self._save()
                else:
                    raise NotImplementedError()
            else:
                raise NoSuchPathError(partial_path)
        else:
            raise NoSuchPathError(partial_path)

    def _db_regex(self, path, partial_path):
        """Generate a regex for determining whether or not a path is in the DB"""
        db_regex_str = "^" + path
        # Assuming that the internal storage is instance number based
        db_regex_str = re.sub(r'\.\*\.', r'.[0-9]+.', db_regex_str)
        db_regex_str = re.sub(r'\.', r'\.', db_regex_str)

        if partial_path:
            db_regex_str = db_regex_str + ".*"

        return db_regex_str

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

        return generic_path

    def _is_meta_parameter(self, path_parts, partial_path_part_len):
        """Determine if the parameter is a meta parameter"""
        return path_parts[partial_path_part_len].startswith("__") and \
               path_parts[partial_path_part_len].endswith("__")

    def _save(self):
        """Save the contents of the DB back into the File"""
        with self._file_write_lock:
            with open(self._db_filename, "w") as db_file:
                json.dump(self._db, db_file, indent=4)

    def reset(self):
        # Retrieve the Persisted Database
        with open(self._db_filename, "r") as db_in_json:
            try:
                self._db = json.load(db_in_json)
            except ValueError as parse_err:
                self._db = {}
                self._log.error("Persisted Database is NOT properly formatted JSON: %s", parse_err)


class NoSuchPathError(Exception):
    """A Database NoSuchPath Error"""
    def __init__(self, value):
        """Initialize the Exception"""
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        """Return the String value of the Exception"""
        return repr(self.value)

#db = Database("erdk-dm.json", "results.json", None)
db = Database("erdk-dm.json", "erdk-db.json", None)
print(db)
#print(db.get("Device."))

"""
result_file = "results.json"

# Retrieve the Implemented Data Model
with open(result_file, "r") as result_in_json:
    try:
        _dm = json.load(result_in_json)['parameters'][0]
        #print(_dm)
        #print(_dm['name'])
        for entry in _dm['value']:
            if entry['dataType'] == 2:
                print("%s:%d" % (entry['name'], int(entry['value'])))
            else:
                if entry['value'] == "":
                    print("%s:\"\"" % (entry['name']))
                else:
                    print("%s:%s" % (entry['name'], entry['value']))
    except ValueError as parse_err:
        _dm = {}
"""
