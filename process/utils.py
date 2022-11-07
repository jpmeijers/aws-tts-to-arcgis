def arcgis_new_feature_no_location(payload, message_time):
    new_feature = {
        "attributes": {
            "location_timestamp": message_time,
        }
    }

    # Add all fields
    new_feature["attributes"].update(payload)

    return new_feature


def arcgis_new_feature_with_location(payload, message_time):
    new_feature = {
        "attributes": {
            "location_timestamp": message_time,
        }
    }

    if "latitude" in payload and "longitude" in payload:
        new_feature["geometry"] = {
            "x": payload["longitude"],
            "y": payload["latitude"],
            "spatialReference": {"wkid": 4326, "latestWkid": 4326}
        }

    # Add all fields
    new_feature["attributes"].update(payload)

    return new_feature


def arcgis_update_feature_no_location(feature, payload, message_time):
    feature.attributes["location_timestamp"] = message_time

    # Add all fields
    feature.attributes.update(payload)

    return feature


def arcgis_update_feature_with_location(feature, payload, message_time):
    feature.attributes["location_timestamp"] = message_time

    if "latitude" in payload and "longitude" in payload:
        if not (payload['latitude'] == 0 and payload['longitude'] == 0):
            feature.geometry = {
                "x": payload["longitude"],
                "y": payload["latitude"],
                "spatialReference": {"wkid": 4326, "latestWkid": 4326}
            }

    # Add all fields
    feature.attributes.update(payload)

    return feature


def flatten_json(y):
    out = {}

    # https://www.geeksforgeeks.org/flattening-json-objects-in-python/
    def flatten(x, name=''):

        # If the Nested key-value
        # pair is of dict type
        if type(x) is dict:

            for a in x:
                flatten(x[a], name + a + '_')

        # If the Nested key-value
        # pair is of list type
        elif type(x) is list:

            i = 0

            for a in x:
                flatten(a, name + str(i) + '_')
                i += 1
        else:
            out[name[:-1]] = x

    flatten(y)
    return out