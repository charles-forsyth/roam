from math import radians, cos, sin, asin, sqrt
from timezonefinder import TimezoneFinder

# Initialize once (heavy)
tf = TimezoneFinder()


def get_timezone_at_point(lat, lng):
    """
    Returns the IANA timezone string (e.g. 'America/New_York') for a lat/lng.
    """
    try:
        return tf.timezone_at(lat=lat, lng=lng) or "UTC"
    except Exception:
        return "UTC"


def decode_polyline(polyline_str):
    """Decodes a Polyline string into a list of lat/lng dicts."""
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {"latitude": 0, "longitude": 0}

    while index < len(polyline_str):
        for unit in ["latitude", "longitude"]:
            shift, result = 0, 0

            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if not byte >= 0x20:
                    break

            if result & 1:
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = result >> 1

        lat += changes["latitude"]
        lng += changes["longitude"]

        coordinates.append({"latitude": lat / 100000.0, "longitude": lng / 100000.0})

    return coordinates


def encode_polyline(points):
    """Encodes a list of lat/lng dicts into a Polyline string."""

    def encode_value(value):
        value = ~(value << 1) if value < 0 else (value << 1)
        chunks = []
        while value >= 0x20:
            chunks.append(chr((0x20 | (value & 0x1F)) + 63))
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
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 3956  # Radius of earth in miles. Use 6371 for km
    return c * r


def get_nearest_point_on_polyline(point_lat, point_lng, polyline_points):
    """
    Finds the nearest point on the polyline.
    Returns (distance_in_miles, index_in_polyline).
    """
    min_dist = float("inf")
    best_index = -1

    # We check every vertex.
    for i, p in enumerate(polyline_points):
        d = haversine_distance(point_lat, point_lng, p["latitude"], p["longitude"])
        if d < min_dist:
            min_dist = d
            best_index = i

    return min_dist, best_index


def calculate_cumulative_distances(polyline_points):
    """
    Returns a list of cumulative distances (in miles) for each point in the polyline.
    """
    distances = [0.0]
    total = 0.0
    for i in range(1, len(polyline_points)):
        p1 = polyline_points[i - 1]
        p2 = polyline_points[i]
        d = haversine_distance(
            p1["latitude"], p1["longitude"], p2["latitude"], p2["longitude"]
        )
        total += d
        distances.append(total)
    return distances


def generate_ascii_chart(data, height=10, width=60):
    """
    Generates a simple ASCII line chart from a list of numbers.
    """
    if not data:
        return ""

    min_val = min(data)
    max_val = max(data)
    range_val = max_val - min_val
    if range_val == 0:
        range_val = 1

    # Normalize data to fit height
    normalized = [int((x - min_val) / range_val * (height - 1)) for x in data]

    # Create grid
    grid = [[" " for _ in range(len(data))] for _ in range(height)]

    for x, y in enumerate(normalized):
        grid[height - 1 - y][x] = "•"

    # Build string
    lines = []

    label_step = range_val / (height - 1)

    for y in range(height):
        val = max_val - (y * label_step)
        label = f"{int(val):>5} |"
        row_str = "".join(grid[y])
        lines.append(f"{label} {row_str}")

    lines.append(f"      0 +{'-' * len(data)}")

    return "\n".join(lines)
