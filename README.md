# WebPA

## Generate the data
http --body "http://tr1d1um.rdkcloud.com:8080/api/v2/device/mac:B827EB5DF064/config?names=Device.WiFi.AccessPoint." Authorization:"Basic XXX" > results.json

## Convert the data
python3 convert.py

## Dump the data
python3 gravity.py. | jq .

# JSON DM from XML
./xml2json -t xml2json -o dm.json --strip_text --strip_namespace --pretty tr-181-2-12-0-usp-full.xml 
