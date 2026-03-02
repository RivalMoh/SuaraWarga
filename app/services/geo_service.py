from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

_geolocator = Nominatim(user_agent="suara_warga_disaster_app_v1")
reverse_geocode = RateLimiter(_geolocator.reverse, min_delay_seconds=1)
forward_geocode = RateLimiter(_geolocator.geocode, min_delay_seconds=1)

def get_location_name(lat: float, lon: float) -> str:
    try:
        location = reverse_geocode((lat, lon), language='id')
        return location.address if location else None
    except Exception as e:
        return None

def get_coordinates(location_name: str) -> dict:
    try:
        location = forward_geocode(location_name, language='id')
        if location:
            return {"latitude": location.latitude, "longitude": location.longitude}
        return None
    except Exception as e:
        pass
    
    return {"lat":None, "lon":None}