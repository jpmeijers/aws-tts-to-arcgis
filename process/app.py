import datetime
import json
import math

import dateutil.parser
import requests
from arcgis.gis import GIS

from utils import arcgis_new_feature_with_location, arcgis_new_feature_no_location, flatten_json, \
    arcgis_update_feature_with_location, arcgis_update_feature_no_location

tts_device_data_cache = dict()


def handler(event, context):
    for record in event['Records']:
        try:
            tts_event = json.loads(record['body'])
            tts_body = json.loads(tts_event['body'])
            tts_domain = tts_event['headers']['x-tts-domain']
            tts_api_key = tts_event['headers']['x-downlink-apikey']

            print("DevID:", tts_body['end_device_ids']['device_id'], tts_domain, tts_api_key)

            # We wrap the actual add to arcgis in a try, to just skip over it when it fails, otherwise we get a queue
            # buildup
            process_message(tts_domain, tts_api_key, tts_body)
        except Exception as error:
            # handle the exception
            print("Process failed:", error)
            print(record)

    return {
        'statusCode': 200,
        'body': ""
    }


def process_message(tts_domain, tts_api_key, post_data):
    device_id = post_data['end_device_ids']['device_id']
    device_eui = post_data['end_device_ids']['dev_eui']
    application_id = post_data['end_device_ids']['application_ids']['application_id']
    print(application_id, device_id, device_eui)

    uplink_time = post_data['received_at']
    uplink_datetime = dateutil.parser.parse(uplink_time)
    print("Uplink time", uplink_datetime)

    # Get the device attributes and name
    url = 'https://' + tts_domain + '/api/v3/applications/' + application_id + '/devices/' + device_id + '?field_mask=name,attributes,locations'

    device_json = None
    if url in tts_device_data_cache:
        device_json = tts_device_data_cache[url]
    else:
        device_response = requests.get(url, headers={"Authorization": "Bearer " + tts_api_key})
        try:
            device_json = device_response.json()
        except:
            return "tts device json error"
        if device_json is None:
            return "tts device json empty"
        # Store in cache
        tts_device_data_cache[url] = device_json

    # print(device_json)

    if 'message' in device_json:
        return device_json['message']

    try:
        name = device_json['name']
    except:
        name = device_id
    try:
        attributes = device_json['attributes']
    except:
        return "device json does not contain attributes"

    print(name)
    # print(attributes)

    try:
        client_id = attributes['arcgis-client-id']
    except:
        return "Attributes does not contain arcgis-client-id"
    try:
        client_secret = attributes['arcgis-client-secret']
    except:
        return "Attributes does not contain arcgis-client-secret"
    try:
        item_id_history = attributes['arcgis-item-id-history']
    except:
        item_id_history = None
        # return "Attributes does not contain arcgis-item-id-history"
    try:
        item_id_last = attributes['arcgis-item-id-last']
    except:
        item_id_last = None
        # return "Attributes does not contain arcgis-item-id-last"

    decoded_payload = post_data['uplink_message']['decoded_payload']
    flat_payload = flatten_json(decoded_payload)
    # print(decoded_payload)
    # print(flat_payload)

    # Use location from console if no location is present in payload
    if 'locations' in device_json:
        if 'user' in device_json['locations']:
            console_latitude = device_json['locations']['user']['latitude']
            console_longitude = device_json['locations']['user']['longitude']
            console_altitude = device_json['locations']['user']['altitude']

            if console_latitude != 0 and console_longitude != 0:
                if not ('latitude' in flat_payload and 'longitude' in flat_payload):
                    flat_payload['latitude'] = console_latitude
                    flat_payload['longitude'] = console_longitude
                    flat_payload['altitude'] = console_altitude

    # If payloads contains a time, use that rather than uplink_datetime
    message_time = uplink_datetime
    if 'timestamp' in flat_payload:
        message_time = datetime.datetime.fromtimestamp(flat_payload['timestamp'])

    # Add device name to payload
    if 'name' not in flat_payload:
        flat_payload['name'] = name

    flat_payload['hardware_serial'] = device_eui

    # Iterate gateways and store stats
    gateway_count = 0
    best_gateway_id = ""
    max_signal = -200
    max_rssi = 0
    max_snr = 0
    for gateway in post_data['uplink_message']['rx_metadata']:
        gateway_count += 1
        if 'rssi' in gateway:
            rssi = gateway['rssi']
            signal = rssi
            if 'snr' in gateway:
                snr = gateway['snr']
                if snr < 0:
                    signal = rssi + snr
            else:
                snr = 0
            if signal > max_signal:
                best_gateway_id = gateway['gateway_ids']['gateway_id']
                max_rssi = rssi
                max_snr = snr
                max_signal = signal
    flat_payload['gateway'] = best_gateway_id
    flat_payload['signal'] = max_signal
    flat_payload['rssi'] = max_rssi
    flat_payload['snr'] = max_snr

    # Get token
    params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': "client_credentials"
    }
    request = requests.get('https://www.arcgis.com/sharing/rest/oauth2/token',
                           params=params)
    response = request.json()
    token = ""
    try:
        token = response["access_token"]
    except:
        print(response)
        return

    gis = GIS(token=token, referer="https://backend.izinto.cloud", expiration=9999)

    # Update "latest" existing feature
    if item_id_last is not None:
        arcgis_item_last = gis.content.get(item_id_last)
        for layer in arcgis_item_last.layers:
            properties = layer.properties
            if 'geometryType' in properties and layer.properties['geometryType'] == 'esriGeometryPoint':
                print("Updating GeometryPoint")
                escapedName = name.replace("'", "''")
                where_clause = f"name='{escapedName}'"
                feature_response = layer.query(where=where_clause)

                if len(feature_response) == 0:
                    print("Creating new feature")
                    # Create a blank feature in case it does not exist yet
                    new_feature = arcgis_new_feature_with_location(flat_payload, message_time)
                    # print(new_feature)
                    result = layer.edit_features(adds=[new_feature])
                    # print(result)

                else:
                    # Only update the first one. Rest should be manually deleted.
                    feature = feature_response.features[0]

                    # Only update if the current message is newer than the last one written to arcgis
                    if math.floor(message_time.timestamp() * 1000) <= feature.attributes['location_timestamp']:
                        print("Feature older than latest")
                        break

                    feature = arcgis_update_feature_with_location(feature, flat_payload, message_time)
                    # print(feature)

                    result = layer.edit_features(updates=[feature])
                    # print(result)

        for table in arcgis_item_last.tables:
            properties = table.properties
            if 'type' in properties and table.properties['type'] == 'Table':
                print("Updating Table")

                where_clause = f"name='{name}'"
                feature_response = table.query(where=where_clause)

                if len(feature_response) == 0:
                    print("Creating new feature")
                    # Create a blank feature in case it does not exist yet
                    new_feature = arcgis_new_feature_no_location(flat_payload, message_time)
                    # print(new_feature)
                    result = table.edit_features(adds=[new_feature])
                    # print(result)

                else:
                    # Only update the first one. Rest should be manually deleted.
                    feature = feature_response.features[0]

                    # Only update if the current message is newer than the last one written to arcgis
                    if math.floor(message_time.timestamp() * 1000) <= feature.attributes['location_timestamp']:
                        print("Feature older than latest")
                        return

                    feature = arcgis_update_feature_no_location(feature, flat_payload, message_time)
                    # print(feature)

                    result = table.edit_features(updates=[feature])
                    # print(result)

    # Append feature to history layer or table
    if item_id_history is not None:
        arcgis_item_history = gis.content.get(item_id_history)
        for layer in arcgis_item_history.layers:
            properties = layer.properties
            if 'geometryType' in properties and layer.properties['geometryType'] == 'esriGeometryPoint':
                print("Adding GeometryPoint")
                new_feature = arcgis_new_feature_with_location(flat_payload, message_time)
                # print(new_feature)
                result = layer.edit_features(adds=[new_feature])
                # print(result)

        for table in arcgis_item_history.tables:
            properties = table.properties
            if 'type' in properties and table.properties['type'] == 'Table':
                print("Adding to Table")
                new_feature = arcgis_new_feature_no_location(flat_payload, message_time)
                # print(new_feature)
                result = table.edit_features(adds=[new_feature])
                # print(result)
