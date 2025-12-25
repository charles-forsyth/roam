from math import radians, cos, sin, asin, sqrt

def decode_polyline(polyline_str):
    """Decodes a Polyline string into a list of lat/lng dicts."""
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}

    while index < len(polyline_str):
        for unit in ['latitude', 'longitude']:
            shift, result = 0, 0

            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1f) << shift
                shift += 5
                if not byte >= 0x20:
                    break

            if (result & 1):
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = (result >> 1)

        lat += changes['latitude']
        lng += changes['longitude']

        coordinates.append({"latitude": lat / 100000.0, "longitude": lng / 100000.0})

    return coordinates

def encode_polyline(points):
    """Encodes a list of lat/lng dicts into a Polyline string."""
    def encode_value(value):
        value = ~(value << 1) if value < 0 else (value << 1)
        chunks = []
        while value >= 0x20:
            chunks.append(chr((0x20 | (value & 0x1f)) + 63))
            value >>= 5
        chunks.append(chr(value + 63))
        return "".join(chunks)

    encoded = []
    prev_lat, prev_lng = 0, 0
    
    for point in points:
        lat = int(round(point["latitude"] * 100000))
        lng = int(round(point["longitude"] * 100000))
        
        encoded.append(encode_value(lat - prev_lat))
        encoded.append(encode_value(lng - prev_lng))
        
        prev_lat, prev_lng = lat, lng
        
    return "".join(encoded)

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    Returns distance in miles.
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 3956 # Radius of earth in miles. Use 6371 for km
    return c * r
