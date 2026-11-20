"""
WeatherGPT - IMD / NDMA Deterministic Hazard & Decision Engine
Ministry of Earth Sciences (MoES / SIH26068)

Calculates:
1. Official IMD/NDMA 4-tier disaster warning matrix (RED, ORANGE, YELLOW, GREEN)
2. Agro-Meteorological Directives (spraying safety, irrigation, harvest preservation)
3. Marine & Fishermen Directives (sea state, venturing clearance, coastal squall risk)
"""

from typing import Dict, Any


def evaluate_hazard_matrix(
    wind_speed: float,
    wind_gusts: float,
    precipitation: float,
    daily_rain: float,
    weather_code: int,
    temp: float
) -> Dict[str, Any]:
    """
    Deterministic IMD / NDMA 4-Tier Disaster Warning Matrix:
    - RED ALERT: Wind >= 62 km/h OR Rain >= 64.5 mm (Disaster protocols)
    - ORANGE ALERT: Wind >= 45 km/h OR Rain >= 35.5 mm (Squalls/heavy rain)
    - YELLOW ALERT: Temp >= 40°C OR Rain >= 15.5 mm OR Wind >= 30 km/h
    - GREEN ALERT: Normal weather conditions
    """
    max_rain = max(precipitation, daily_rain)
    max_wind = max(wind_speed, wind_gusts * 0.85)

    # 1. RED ALERT EVALUATION
    if max_wind >= 62.0 or max_rain >= 64.5 or (weather_code in [82, 99] and max_wind >= 55.0):
        level = "RED"
        title_en = "RED ALERT (Take Action / Warning)"
        title_hi = "रेड अलर्ट (तत्काल कार्रवाई करें / गंभीर चेतावनी)"
        color = "#dc2626"
        bg_color = "rgba(239, 68, 68, 0.15)"
        border_color = "#b91c1c"
        badge_text = "DANGER / TAKE ACTION"
        hazard_type = (
            "Gale-force Cyclonic Wind & Severe Storm Hazard"
            if max_wind >= 62.0
            else "Extremely Heavy Inundation & Flash Flood Hazard"
        )
        instructions_en = (
            "Life-threatening conditions imminent. Suspend all outdoor, port, and agricultural operations. "
            "Evacuate vulnerable low-lying areas. Move to designated storm/cyclone shelters immediately."
        )
        instructions_hi = (
            "अत्यधिक गंभीर स्थिति। सभी बाहरी, कृषि एवं बंदरगाह गतिविधियाँ तत्काल स्थगित करें। "
            "निचले इलाकों से सुरक्षित स्थानों पर जाएँ और आपदा राहत केंद्रों में शरण लें।"
        )

    # 2. ORANGE ALERT EVALUATION
    elif max_wind >= 45.0 or max_rain >= 35.5 or (weather_code in [95, 96] and max_wind >= 40.0):
        level = "ORANGE"
        title_en = "ORANGE ALERT (Be Prepared / Severe Weather)"
        title_hi = "ऑरेंज अलर्ट (तैयार रहें / गंभीर मौसम)"
        color = "#ea580c"
        bg_color = "rgba(249, 115, 22, 0.15)"
        border_color = "#c2410c"
        badge_text = "HIGH ALERT / BE PREPARED"
        if max_rain >= 35.5 and max_wind >= 45.0:
            hazard_type = "Squall Line, Gusty Gales & Heavy Downpour"
        elif max_wind >= 45.0:
            hazard_type = "Squall Line & Severe Gusty Gales Hazard"
        else:
            hazard_type = "Heavy Downpour & Flash Inundation Hazard"
        instructions_en = (
            "Significant risk to life and property. Secure loose rooftop structures, prepare emergency disaster kits "
            "(potable water, torch, medical kit), and avoid non-essential travel."
        )
        instructions_hi = (
            "जीवन एवं संपत्ति के लिए बड़ा ख़तरा। आपातकालीन किट तैयार रखें, गैर-जरूरी यात्रा से बचें "
            "और मजबूत पक्के भवनों में सुरक्षित रहें।"
        )

    # 3. YELLOW ALERT EVALUATION
    elif temp >= 40.0 or max_rain >= 15.5 or max_wind >= 30.0 or weather_code in [95, 96, 99]:
        level = "YELLOW"
        title_en = "YELLOW ALERT (Be Updated / Moderate Risk)"
        title_hi = "येलो अलर्ट (सतर्क रहें / जानकारी रखें)"
        color = "#d97706"
        bg_color = "rgba(245, 158, 11, 0.15)"
        border_color = "#b45309"
        badge_text = "WATCH / BE UPDATED"
        if temp >= 40.0:
            hazard_type = "Severe Heatwave Stress (>40°C)"
        elif max_rain >= 15.5:
            hazard_type = "Moderate Thunderstorm, Rain & Localized Inundation"
        elif weather_code in [95, 96, 99]:
            hazard_type = "Thunderstorm & Localized Squalls"
        else:
            hazard_type = "Moderate Surface Wind Gusts & Squalls"
        instructions_en = (
            "Weather conditions may deteriorate. Track official IMD weather bulletins. "
            "Farmers, coastal workers, and commuters should exercise vigilance."
        )
        instructions_hi = (
            "मौसम की स्थिति बिगड़ सकती है। मौसम विभाग (IMD) की नियमित चेतावनियों पर नज़र रखें। "
            "खुले स्थानों और पेड़ों के नीचे शरण न लें।"
        )

    # 4. GREEN NORMAL EVALUATION
    else:
        level = "GREEN"
        title_en = "GREEN ALERT (Normal Weather / No Warning)"
        title_hi = "ग्रीन अलर्ट (सामान्य मौसम / कोई चेतावनी नहीं)"
        color = "#059669"
        bg_color = "rgba(16, 185, 129, 0.15)"
        border_color = "#047857"
        badge_text = "NORMAL / NO ADVERSE WARNING"
        hazard_type = "Favorable Atmospheric Conditions"
        instructions_en = (
            "No adverse weather warning. Routine agricultural, marine, transportation, and daily commercial activities "
            "can proceed safely as scheduled."
        )
        instructions_hi = (
            "कोई प्रतिकूल चेतावनी नहीं। दैनिक कार्य, खेती और व्यापारिक गतिविधियाँ सामान्य रूप से जारी रखी जा सकती हैं।"
        )

    return {
        "level": level,
        "title_en": title_en,
        "title_hi": title_hi,
        "color": color,
        "bg_color": bg_color,
        "border_color": border_color,
        "badge_text": badge_text,
        "hazard_type": hazard_type,
        "instructions_en": instructions_en,
        "instructions_hi": instructions_hi,
        "wind_trigger_val": round(wind_speed, 1),
        "gust_trigger_val": round(wind_gusts, 1),
        "rain_trigger_val": round(daily_rain, 1)
    }


def compute_agro_advisory(
    wind_speed: float,
    precipitation: float,
    humidity: float,
    temp: float,
    weather_code: int,
    alert_level: str = "GREEN",
    daily_rain: float = 0.0
) -> Dict[str, Any]:
    """
    Agro-Meteorological Directive Engine (GKMS / ICAR / IMD Protocols):
    - Spraying Safety: Wind < 15 km/h & Rain <= 0.5 mm
    - Irrigation Management: Suspend on Rain >= 10 mm; Micro-irrigate on Temp >= 38°C
    - Harvesting: Strictly avoid during adverse conditions (YELLOW/ORANGE/RED, Rain > 0 mm, Humidity > 80%)
    """
    # 1. Chemical Spraying Window Evaluation
    if wind_speed > 15.0 and precipitation > 0.5:
        spraying_status = "UNSAFE"
        spraying_color = "#ef4444"
        spraying_desc_en = f"Unsafe Window (Sustained Wind: {wind_speed:.1f} km/h, Rain: {precipitation:.1f} mm) — High chemical drift and wash-off risk."
        spraying_desc_hi = f"असुरक्षित (स्थिर पवन: {wind_speed:.1f} km/h, वर्षा: {precipitation:.1f} mm) — कीटनाशक बहने एवं बिखरने का भारी जोखिम।"
    elif wind_speed > 15.0:
        spraying_status = "CAUTION"
        spraying_color = "#f59e0b"
        spraying_desc_en = f"Caution (Sustained Wind: {wind_speed:.1f} km/h > 15 km/h limit) — Spray drift risk; postpone foliar pesticide applications."
        spraying_desc_hi = f"सावधानी (स्थिर पवन: {wind_speed:.1f} km/h > 15 km/h) — कीटनाशक हवा में उड़ने का ख़तरा; छिड़काव स्थगित रखें।"
    elif precipitation > 0.5:
        spraying_status = "UNSAFE"
        spraying_color = "#ef4444"
        spraying_desc_en = f"Unsafe (Rain: {precipitation:.1f} mm) — Chemical wash-off risk; postpone all agrochemical spraying."
        spraying_desc_hi = f"असुरक्षित (वर्षा: {precipitation:.1f} mm) — कीटनाशक धुलने का ख़तरा; सभी छिड़काव रोकें।"
    else:
        spraying_status = "OPTIMAL"
        spraying_color = "#10b981"
        spraying_desc_en = f"Optimal Window (Sustained Wind: {wind_speed:.1f} km/h, Dry canopy) — Ideal conditions for foliar nutrients and pest control."
        spraying_desc_hi = f"उत्तम समय (शांत पवन {wind_speed:.1f} km/h, सूखा मौसम) — कीटनाशक एवं पोषण छिड़काव के लिए अनुकूल समय।"

    # 2. Irrigation Directive
    if precipitation >= 10.0 or daily_rain >= 15.0:
        irrigation_en = "Suspend field irrigation immediately. Ensure proper drainage channels to prevent root hypoxia and waterlogging."
        irrigation_hi = "सिंचाई तुरंत रोकें। खेतों से अतिरिक्त जल निकासी की व्यवस्था करें ताकि फसलों में जलभराव न हो।"
    elif temp >= 38.0:
        irrigation_en = "Elevated evapotranspiration demand. Apply light micro-irrigation during early morning or late dusk hours."
        irrigation_hi = "तीव्र वाष्पीकरण। सुबह जल्दी या शाम के समय हल्की एवं निरंतर सिंचाई करें।"
    else:
        irrigation_en = "Adequate soil moisture status. Maintain standard crop irrigation intervals."
        irrigation_hi = "सामान्य नमी स्तर। फसल की आवश्यकतानुसार नियमित अंतराल पर सिंचाई जारी रखें।"

    # 3. Harvesting & Produce Protection
    # Rule: NEVER show "favorable for harvesting, threshing, sun-drying" when alert level is YELLOW, ORANGE, or RED,
    # OR when precipitation > 0 mm (or daily_rain > 0 mm), OR when humidity > 80%.
    is_adverse_harvest = (
        alert_level.upper() in ["YELLOW", "ORANGE", "RED"]
        or precipitation > 0.0
        or daily_rain > 0.0
        or humidity > 80.0
        or wind_speed > 35.0
        or weather_code in [80, 81, 82, 95, 96, 99]
    )

    if is_adverse_harvest:
        harvesting_en = "STRICTLY AVOID HARVESTING & SUN-DRYING: High moisture and squall risk; cover harvested produce with waterproof tarpaulins immediately."
        harvesting_hi = "कटाई एवं धूप में सुखाने से पूरी तरह बचें: अत्यधिक नमी व आंधी का ख़तरा; कटी फसलों को तुरंत वाटरप्रूफ तिरपाल से सुरक्षित ढकें।"
    else:
        harvesting_en = "Atmospheric conditions favorable for harvesting, threshing, sun-drying, and storage."
        harvesting_hi = "फसल कटाई, मड़ाई एवं धूप में सुखाने के लिए मौसम पूरी तरह अनुकूल है।"

    return {
        "spraying_status": spraying_status,
        "spraying_color": spraying_color,
        "spraying_desc_en": spraying_desc_en,
        "spraying_desc_hi": spraying_desc_hi,
        "irrigation_en": irrigation_en,
        "irrigation_hi": irrigation_hi,
        "harvesting_en": harvesting_en,
        "harvesting_hi": harvesting_hi
    }


def compute_marine_advisory(
    wind_speed: float,
    wind_gusts: float,
    precipitation: float,
    is_coastal: bool
) -> Dict[str, Any]:
    """
    Marine & Fishermen Directive Engine (INCOIS / IMD Marine Protocols):
    - Wind >= 62 km/h: Total Ban on Deep-Sea Venturing (Phenomenal/Very Rough Sea)
    - Wind 45-61 km/h: Warning; Return to harbor immediately
    - Wind 30-44 km/h: Caution for small artisanal craft
    - Wind < 30 km/h: Safe for all maritime operations
    """
    max_wind = max(wind_speed, wind_gusts)
    wind_label_en = f"Sustained: {wind_speed:.1f} km/h, Peak Gusts: {wind_gusts:.1f} km/h"
    wind_label_hi = f"स्थिर पवन: {wind_speed:.1f} km/h, तेज झोंके: {wind_gusts:.1f} km/h"

    if max_wind >= 62.0:
        status = "CRITICAL HAZARD"
        sea_state_en = f"Very Rough to Phenomenal Sea ({wind_label_en})"
        sea_state_hi = f"अत्यंत अशांत एवं प्रचंड समुद्र ({wind_label_hi})"
        color = "#ef4444"
        venture_safe = False
        advisory_en = "TOTAL BAN ON SEA VENTURING. Fishermen are strictly advised NOT to venture into deep sea or coastal waters. Secure all mechanized boats ashore."
        advisory_hi = "समुद्र में जाने पर पूर्ण प्रतिबंध! मछुआरे गहरे समुद्र या तट के पास कतई न जाएँ। नावों को सुरक्षित स्थानों पर बाँधें।"
    elif max_wind >= 45.0:
        status = "WARNING"
        sea_state_en = f"Rough to Very Rough Sea ({wind_label_en})"
        sea_state_hi = f"अशांत समुद्र ({wind_label_hi})"
        color = "#f97316"
        venture_safe = False
        advisory_en = "HIGH RISK. Fishermen in deep sea are advised to return to harbor immediately. Artisanal and non-mechanized craft operations suspended."
        advisory_hi = "उच्च जोखिम। गहरे समुद्र में गए मछुआरे तत्काल तट पर लौट आएँ। छोटी नावों का परिचालन स्थगित रखें।"
    elif max_wind >= 30.0:
        status = "CAUTION"
        sea_state_en = f"Moderate to Squally Conditions ({wind_label_en})"
        sea_state_hi = f"मध्यम से तेज समुद्री हवाएँ ({wind_label_hi})"
        color = "#eab308"
        venture_safe = True
        advisory_en = "EXERCISE CAUTION. Artisanal boat operators should stay close to coastline and avoid venturing into deep sea."
        advisory_hi = "सतर्कता बरतें। छोटी नाव चालक गहरे समुद्र में जाने से बचें एवं तट के निकट ही रहें।"
    else:
        status = "SAFE"
        sea_state_en = f"Smooth to Slight Sea ({wind_label_en})"
        sea_state_hi = f"शांत एवं अनुकूल समुद्र ({wind_label_hi})"
        color = "#10b981"
        venture_safe = True
        advisory_en = "SAFE FOR FISHING. Sea conditions are calm and favorable for routine coastal and deep-sea operations."
        advisory_hi = "मत्स्य पालन हेतु सुरक्षित। समुद्र शांत है एवं सामान्य मछली पकड़ने के लिए स्थिति अनुकूल है।"

    return {
        "status": status,
        "sea_state_en": sea_state_en,
        "sea_state_hi": sea_state_hi,
        "color": color,
        "venture_safe": venture_safe,
        "advisory_en": advisory_en,
        "advisory_hi": advisory_hi,
        "is_coastal_region": is_coastal
    }


def compute_urban_advisory(
    wind_speed: float,
    wind_gusts: float,
    precipitation: float,
    daily_rain: float,
    temp: float,
    humidity: float,
    weather_code: int,
    alert_level: str = "GREEN"
) -> Dict[str, Any]:
    """
    Urban & Surface Transport / Infrastructure Advisory Engine (NDMA / MoRTH Standards):
    Designed for landlocked / inland districts where maritime directives are inapplicable.
    Covers:
    1. Road visibility & surface transit precautions
    2. Urban waterlogging & underpass drainage
    3. Power-line, overhead cables & structural wind safety
    4. Heat-stress / public health precautions
    """
    max_wind = max(wind_speed, wind_gusts)
    max_rain = max(precipitation, daily_rain)
    level = alert_level.upper()

    # Overall Urban Transit Status
    if level == "RED" or max_wind >= 62.0 or max_rain >= 64.5:
        status = "CRITICAL HAZARD"
        color = "#ef4444"
    elif level == "ORANGE" or max_wind >= 45.0 or max_rain >= 35.5:
        status = "HIGH ALERT"
        color = "#f97316"
    elif level == "YELLOW" or max_wind >= 30.0 or max_rain >= 15.5 or temp >= 40.0:
        status = "CAUTION"
        color = "#eab308"
    else:
        status = "NORMAL TRANSIT"
        color = "#10b981"

    # 1. Road Visibility & Traffic Precautions
    if weather_code in [45, 48]:
        visibility_en = "Dense fog restricting surface visibility (< 200m). Use low-beam fog lamps, reduce highway speeds, and maintain safe braking distance."
        visibility_hi = "घना कोहरा छाए रहने से दृश्यता अत्यंत कम (< 200 मी)। फॉग लैंप का उपयोग करें, गति धीमी रखें और वाहनों से सुरक्षित दूरी बनाए रखें।"
    elif max_rain >= 35.5 or weather_code in [82, 95, 96, 99]:
        visibility_en = "Intense torrential downpours causing sharp drop in road visibility and severe aquaplaning hazard. Delay non-essential road travel."
        visibility_hi = "मूसलाधार बारिश से दृश्यता में भारी कमी एवं सड़कों पर तीव्र फिसलन का ख़तरा। गैर-जरूरी सड़क यात्रा टालने की सलाह है।"
    elif max_rain > 0.0 or weather_code in [51, 53, 55, 61, 63, 65, 80, 81]:
        visibility_en = f"Wet pavement and slick road surfaces (Recorded rain: {max_rain:.1f} mm). Exercise caution at turns and highway interchanges."
        visibility_hi = f"सड़कें गीली एवं फिसलन भरी हैं (दर्ज वर्षा: {max_rain:.1f} mm)। मोड़ों एवं व्यस्त चौराहों पर सावधानीपूर्वक वाहन चलाएँ।"
    else:
        visibility_en = "Optimal road visibility and clear arterial corridors. Surface transit operating normally without atmospheric impediments."
        visibility_hi = "सड़क दृश्यता उत्तम एवं स्पष्ट। सड़क यातायात बिना किसी मौसमी रुकावट के सामान्य रूप से संचालित है।"

    # 2. Urban Waterlogging & Drainage
    if max_rain >= 64.5:
        waterlogging_en = f"Severe inundation risk (24h Rain: {max_rain:.1f} mm). Low-lying subway underpasses and basement parking vulnerable; avoid submerged roads."
        waterlogging_hi = f"गंभीर जलभराव का ख़तरा (24 घंटे में वर्षा: {max_rain:.1f} mm)। निचले अंडरपास एवं बेसमेंट पार्किंग से बचें; जलमग्न मार्गों पर वाहन न ले जाएँ।"
    elif max_rain >= 15.5:
        waterlogging_en = "Localized water accumulation likely in low-lying corridors and poor drainage sectors. Municipal stormwater pumping recommended."
        waterlogging_hi = "निचले इलाकों एवं खराब जल निकासी वाले चौराहों पर जलभराव संभव। वैकल्पिक मार्गों का प्रयोग करें और नगर निगम अलर्ट पर रहे।"
    else:
        waterlogging_en = "Zero waterlogging hazard detected. Stormwater channels and urban transit corridors flowing freely."
        waterlogging_hi = "जलभराव का कोई ख़तरा नहीं। शहरी नालियां और मुख्य मार्ग पूरी तरह साफ़ एवं सुचारू हैं।"

    # 3. Power-Line, Overhead Cables & Wind Safety
    if wind_gusts >= 60.0 or wind_speed >= 45.0:
        wind_safety_en = f"Gale-force squalls (Peak Gusts: {wind_gusts:.1f} km/h, Sustained: {wind_speed:.1f} km/h). Extreme hazard of snapped live wires and falling tree branches; keep clear of overhead lines."
        wind_safety_hi = f"भीषण आंधी का ख़तरा (तेज झोंके: {wind_gusts:.1f} km/h, स्थिर पवन: {wind_speed:.1f} km/h)। बिजली के तार टूटने व पेड़ गिरने का अत्यधिक ख़तरा; बिजली खंभों से दूर रहें।"
    elif wind_gusts >= 35.0 or wind_speed >= 25.0:
        wind_safety_en = f"Gusty surface winds (Peak Gusts: {wind_gusts:.1f} km/h, Sustained: {wind_speed:.1f} km/h). Secure tin rooftops and loose roadside hoardings; avoid parking vehicles under fragile trees."
        wind_safety_hi = f"तेज झोंकेदार हवाएँ (झोंके: {wind_gusts:.1f} km/h, स्थिर पवन: {wind_speed:.1f} km/h)। टिन शेड और साइनबोर्ड सुरक्षित करें; वाहनों को पुराने पेड़ों के नीचे खड़ा न करें।"
    else:
        wind_safety_en = f"Stable wind profile (Sustained: {wind_speed:.1f} km/h, Peak Gusts: {wind_gusts:.1f} km/h). Power transmission lines, telecom towers, and structural installations fully safe."
        wind_safety_hi = f"सामान्य एवं शांत हवा (स्थिर: {wind_speed:.1f} km/h, झोंके: {wind_gusts:.1f} km/h)। विद्युत ग्रिड एवं संचार टावर पूरी तरह सुरक्षित हैं।"

    # 4. Heat-Stress & Public Transit Precautions
    if temp >= 40.0:
        heat_stress_en = f"Severe heatwave stress ({temp:.1f}°C). High heatstroke risk; avoid direct sun exposure between 11 AM - 4 PM and maintain oral rehydration."
        heat_stress_hi = f"तीव्र लू एवं हीटवेव की स्थिति ({temp:.1f}°C)। डिहाइड्रेशन व हीटस्ट्रोक से बचें, दोपहर 11 से 4 बजे धूप में न निकलें और ओआरएस/पानी पीते रहें।"
    elif temp >= 35.0 and humidity >= 70:
        heat_stress_en = f"Elevated sultriness (Temp: {temp:.1f}°C, Humidity: {humidity}%). High thermal discomfort; public transit commuters advised to stay well hydrated."
        heat_stress_hi = f"अत्यधिक उमस व गर्मी (तापमान: {temp:.1f}°C, नमी: {humidity}%)। सार्वजनिक परिवहन यात्रियों को पर्याप्त पानी पीने और सतर्क रहने की सलाह।"
    elif temp <= 8.0:
        heat_stress_en = f"Cold-wave conditions ({temp:.1f}°C). Vulnerable groups and night commuters must wear layered thermal clothing."
        heat_stress_hi = f"शीतलहर का प्रभाव ({temp:.1f}°C)। रात्रि यात्रियों एवं बच्चों/बुजुर्गों को गर्म व ऊनी कपड़े पहनने की सलाह है।"
    else:
        heat_stress_en = f"Surface thermal conditions within comfortable thresholds ({temp:.1f}°C, Humidity: {humidity}%). Safe for all routine urban commuting and outdoor activity."
        heat_stress_hi = f"तापमान एवं मौसम अनुकूल ({temp:.1f}°C, नमी: {humidity}%)। सामान्य आवागमन एवं बाहरी कार्यों के लिए स्थिति पूरी तरह सुरक्षित है।"

    return {
        "status": status,
        "color": color,
        "visibility_en": visibility_en,
        "visibility_hi": visibility_hi,
        "waterlogging_en": waterlogging_en,
        "waterlogging_hi": waterlogging_hi,
        "wind_safety_en": wind_safety_en,
        "wind_safety_hi": wind_safety_hi,
        "heat_stress_en": heat_stress_en,
        "heat_stress_hi": heat_stress_hi,
        "is_urban_inland": True
    }
