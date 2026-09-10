"""
WeatherGPT - Weather & Geocoding Service
Ministry of Earth Sciences (MoES / SIH26068)

Asynchronous meteorological data ingestion using httpx, dynamic geocoding for Indian
districts with robust state-level prioritization, and coordinate-based in-memory caching.
"""

import time
import re
import unicodedata
import logging
from typing import Dict, Any, Optional, Tuple, List
import httpx
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger("WeatherGPT.WeatherService")

# Known coastal states, union territories, and coastal administrative regions in India
COASTAL_REGIONS = {
    "odisha", "orissa", "andhra pradesh", "west bengal", "tamil nadu",
    "kerala", "karnataka", "goa", "maharashtra", "gujarat",
    "puducherry", "pondicherry", "andaman and nicobar islands",
    "lakshadweep", "daman and diu", "dadra and nagar haveli and daman and diu"
}

COASTAL_KEYWORDS = {
    "coast", "coastal", "port", "beach", "island", "sea", "bay", "creek", "harbor", "harbour", "gulf"
}

# Known administrative aliases/spelling variants for Indian districts and divisions
DISTRICT_SPELLING_VARIANTS = {
    "jajapur": ["Jajpur", "Jajapur"],
    "khorda": ["Khordha", "Khurda", "Bhubaneswar", "Khorda"],
    "baleswar": ["Balasore", "Baleswar"],
    "cuttack north": ["Cuttack"],
    "cuttack south": ["Cuttack"],
    "mumbai south": ["Mumbai"],
    "mumbai city": ["Mumbai"],
    "mumbai suburban": ["Mumbai"],
    "central delhi": ["Delhi", "New Delhi"],
    "new delhi": ["Delhi", "New Delhi"],
    "kolkata central": ["Kolkata"],
    "chennai gpo": ["Chennai"]
}


class LocationNotFoundError(Exception):
    """Raised when a geocoding query yields no valid geographical coordinates for the target district."""
    pass


def clean_diacritics(text: str) -> str:
    """Normalize unicode diacritics into standard ASCII (e.g., Jājpur -> Jajpur, Khordhā -> Khordha)."""
    normalized = unicodedata.normalize('NFKD', text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


class WeatherService:
    """Asynchronous service for geocoding and live meteorological data ingestion."""

    def __init__(self):
        # In-memory coordinate cache: (lat_round, lon_round) -> (timestamp, telemetry_dict)
        self._telemetry_cache: Dict[Tuple[float, float], Tuple[float, Dict[str, Any]]] = {}

    def _is_coastal_region(self, name: str, state: str, country: str) -> Tuple[bool, str]:
        """Heuristically determine coastal classification and maritime proximity."""
        full_text = f"{name} {state} {country}".lower()
        
        # Check keyword matches
        if any(kw in full_text for kw in COASTAL_KEYWORDS):
            return True, "Direct Coastal / Maritime Zone"
            
        # Check known coastal state/UT
        state_clean = state.strip().lower().replace("orissa", "odisha")
        for c_state in COASTAL_REGIONS:
            if c_state in state_clean or state_clean in c_state:
                return True, f"Coastal Belt ({state})"
                
        return False, "Inland Plains / Continental Zone"

    async def _resolve_pincode_details(self, pincode: str, client: httpx.AsyncClient) -> Optional[Dict[str, str]]:
        """Resolve 6-digit Indian PIN code to administrative postal metadata."""
        try:
            url = f"https://api.postalpincode.in/pincode/{pincode}"
            res = await client.get(url, timeout=4.0)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) > 0 and data[0].get("Status") == "Success":
                    po_list = data[0].get("PostOffice", [])
                    if po_list:
                        po = po_list[0]
                        return {
                            "district": po.get("District", ""),
                            "division": po.get("Division", ""),
                            "state": po.get("State", ""),
                            "block": po.get("Block", ""),
                            "name": po.get("Name", ""),
                            "pincode": pincode
                        }
        except Exception as err:
            logger.warning(f"Indian postal geocoding lookup error for {pincode}: {err}")
        return None

    async def resolve_coordinates(self, location_query: str) -> Dict[str, Any]:
        """
        Dynamically geocode target Indian district via Open-Meteo Geocoding API
        with state-level prioritization and postal resolution.
        
        Returns:
            Dict containing place name, state, country, latitude, longitude, elevation, and coastal status.
        """
        clean_query = location_query.strip()
        if not clean_query:
            raise LocationNotFoundError("District query cannot be empty.")

        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            # 1. Detect 6-digit Indian PIN code
            pin_match = re.search(r"\b[1-9][0-9]{5}\b", clean_query)
            pincode = pin_match.group(0) if pin_match else None
            
            postal_info = None
            if pincode:
                postal_info = await self._resolve_pincode_details(pincode, client)

            # 2. Extract Clean Place Name & Target State Hint
            query_without_pin = re.sub(r"\b[1-9][0-9]{5}\b", "", clean_query)
            query_without_pin = re.sub(r"[,/\\-]", " ", query_without_pin).strip()
            
            state_hint = postal_info["state"] if postal_info else ""
            
            # Check if user entered "City, State" (e.g., "Cuttack, Odisha")
            if "," in clean_query and not pincode:
                parts = [p.strip() for p in clean_query.split(",")]
                primary_name = parts[0]
                if len(parts) > 1:
                    state_hint = parts[1]
            elif query_without_pin:
                primary_name = query_without_pin
                # Remove state name if entered inline (e.g. "Jajpur Odisha")
                if postal_info and postal_info["state"].lower() in primary_name.lower():
                    primary_name = re.sub(re.escape(postal_info["state"]), "", primary_name, flags=re.IGNORECASE).strip()
            else:
                primary_name = ""

            # Build prioritized list of candidate place names to search
            candidates: List[str] = []
            if primary_name:
                cleaned_primary = clean_diacritics(primary_name)
                candidates.append(cleaned_primary)
                # Check for known variants (e.g. Jajapur -> Jajpur)
                if cleaned_primary.lower() in DISTRICT_SPELLING_VARIANTS:
                    candidates.extend(DISTRICT_SPELLING_VARIANTS[cleaned_primary.lower()])

            if postal_info:
                dist = clean_diacritics(postal_info.get("district", ""))
                div = clean_diacritics(postal_info.get("division", ""))
                po_name = clean_diacritics(postal_info.get("name", ""))

                for field_val in [dist, div, po_name]:
                    if field_val:
                        low = field_val.lower()
                        if low in DISTRICT_SPELLING_VARIANTS:
                            candidates.extend(DISTRICT_SPELLING_VARIANTS[low])
                        else:
                            candidates.append(field_val)

            if not candidates:
                candidates.append(clean_query)

            # Deduplicate candidates preserving priority order
            unique_candidates: List[str] = []
            for c in candidates:
                c_clean = c.strip()
                if c_clean and c_clean not in unique_candidates:
                    unique_candidates.append(c_clean)

            # 3. Query Open-Meteo with Country Bias & State Prioritization
            target_state_clean = (state_hint or "").strip().lower().replace("orissa", "odisha")
            selected_match = None
            matched_candidate = unique_candidates[0]

            for cand in unique_candidates:
                params = {
                    "name": cand,
                    "count": 5,
                    "country_code": "IN",
                    "language": "en",
                    "format": "json"
                }

                try:
                    response = await client.get(settings.geocoding_api_url, params=params)
                    if response.status_code == 200:
                        results = response.json().get("results", [])
                        
                        # Filter for Indian locations
                        india_results = [
                            r for r in results 
                            if r.get("country_code", "").upper() == "IN" or "india" in r.get("country", "").lower()
                        ]

                        if not india_results and results:
                            india_results = results

                        # If state hint is available, look for exact state match
                        if target_state_clean:
                            for item in india_results:
                                admin1 = item.get("admin1", "").lower().replace("orissa", "odisha")
                                admin2 = item.get("admin2", "").lower().replace("orissa", "odisha")
                                if (target_state_clean in admin1 or admin1 in target_state_clean or
                                    target_state_clean in admin2 or admin2 in target_state_clean):
                                    selected_match = item
                                    matched_candidate = cand
                                    break

                        # If no state match or no state hint, choose top Indian result
                        if not selected_match and india_results and not target_state_clean:
                            selected_match = india_results[0]
                            matched_candidate = cand
                            break

                except Exception as exc:
                    logger.warning(f"Geocoding candidate attempt failed for '{cand}': {exc}")

                if selected_match:
                    break

            # Final fallback: search clean query directly
            if not selected_match:
                params = {"name": f"{clean_query}, India", "count": 5, "language": "en", "format": "json"}
                res = await client.get(settings.geocoding_api_url, params=params)
                if res.status_code == 200 and res.json().get("results"):
                    selected_match = res.json()["results"][0]

            if not selected_match:
                logger.warning(f"No geocoding match found for: '{clean_query}'")
                raise LocationNotFoundError(f"District '{clean_query}' could not be resolved. Please verify the spelling or include the state (e.g., 'Khordha, Odisha').")

            raw_name = clean_diacritics(selected_match.get("name", matched_candidate.capitalize()))
            state_name = (
                selected_match.get("admin1") or 
                selected_match.get("admin2") or 
                (postal_info.get("state") if postal_info else "") or 
                selected_match.get("country", "India")
            )
            country_name = selected_match.get("country", "India")
            lat = float(selected_match["latitude"])
            lon = float(selected_match["longitude"])
            elevation = float(selected_match.get("elevation", 20.0))

            display_name = raw_name
            if pincode:
                display_name = f"{raw_name} (PIN {pincode})"

            is_coastal, proximity = self._is_coastal_region(raw_name, state_name, country_name)

            return {
                "name": display_name,
                "state": state_name,
                "country": country_name,
                "latitude": lat,
                "longitude": lon,
                "elevation": elevation,
                "is_coastal": is_coastal,
                "coastal_proximity": proximity,
                "query": clean_query
            }

    async def get_live_metrics(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Fetch live meteorological telemetry from Open-Meteo High-Resolution API.
        Applies in-memory coordinate-based caching with TTL to eliminate duplicate upstream queries.
        """
        cache_key = (round(lat, 2), round(lon, 2))
        now = time.time()

        # Check Cache
        if cache_key in self._telemetry_cache:
            timestamp, cached_data = self._telemetry_cache[cache_key]
            if (now - timestamp) < settings.cache_ttl_seconds:
                logger.info(f"Serving cached meteorological telemetry for coordinates {cache_key}")
                return cached_data

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "is_day",
                "precipitation",
                "rain",
                "showers",
                "weather_code",
                "cloud_cover",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m"
            ],
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "wind_speed_10m_max",
                "wind_gusts_10m_max"
            ],
            "timezone": "auto"
        }

        try:
            async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
                response = await client.get(settings.weather_api_url, params=params)

            if response.status_code == 200:
                raw_data = response.json()
                current = raw_data.get("current", {})
                daily = raw_data.get("daily", {})

                precip_sums = daily.get("precipitation_sum", [0.0])
                daily_rain = float(precip_sums[0]) if precip_sums and precip_sums[0] is not None else 0.0

                wind_max_list = daily.get("wind_speed_10m_max", [current.get("wind_speed_10m", 0.0)])
                daily_wind_max = float(wind_max_list[0]) if wind_max_list and wind_max_list[0] is not None else float(current.get("wind_speed_10m", 0.0))

                telemetry = {
                    "temperature_c": float(current.get("temperature_2m", 25.0)),
                    "apparent_temperature_c": float(current.get("apparent_temperature", 26.0)),
                    "humidity_percent": int(current.get("relative_humidity_2m", 60)),
                    "precipitation_mm": float(current.get("precipitation", 0.0)),
                    "wind_speed_kmh": float(current.get("wind_speed_10m", 10.0)),
                    "wind_gusts_kmh": float(current.get("wind_gusts_10m", 14.0)),
                    "wind_direction_deg": int(current.get("wind_direction_10m", 0)),
                    "cloud_cover_percent": int(current.get("cloud_cover", 20)),
                    "is_day": int(current.get("is_day", 1)),
                    "weather_code": int(current.get("weather_code", 0)),
                    "daily_rain_total_mm": daily_rain,
                    "daily_wind_max_kmh": daily_wind_max
                }

                # Store in cache
                self._telemetry_cache[cache_key] = (now, telemetry)
                return telemetry

            else:
                logger.error(f"Open-Meteo Forecast API error: HTTP {response.status_code} - {response.text}")
                raise HTTPException(status_code=502, detail="Upstream meteorological telemetry provider error.")

        except httpx.RequestError as exc:
            logger.error(f"Network error fetching telemetry for ({lat}, {lon}): {exc}")
            # If cache has an expired copy, fallback to it during network drops
            if cache_key in self._telemetry_cache:
                logger.warning("Network failed; falling back to stale cached telemetry.")
                return self._telemetry_cache[cache_key][1]
            raise HTTPException(status_code=503, detail=f"Meteorological telemetry ingestion failure: {str(exc)}")


# Global singleton service instance
weather_service = WeatherService()
