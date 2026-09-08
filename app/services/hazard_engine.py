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
        title_or = "ରେଡ୍ ଆଲର୍ଟ (ତୁରନ୍ତ ପଦକ୍ଷେପ ନିଅନ୍ତୁ / ବିପଜ୍ଜନକ ସତର୍କତା)"
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
        instructions_or = (
            "ଅତ୍ୟନ୍ତ ବିପଜ୍ଜନକ ପରିସ୍ଥିତି। ସମସ୍ତ ବାହ୍ୟ କାର୍ଯ୍ୟ, କୃଷି ଓ ବନ୍ଦର କାର୍ଯ୍ୟ ବନ୍ଦ ରଖନ୍ତୁ। "
            "ତୁରନ୍ତ ବାତ୍ୟା/ବନ୍ୟା ଆଶ୍ରୟସ୍ଥଳୀକୁ ସ୍ଥାନାନ୍ତର ହୁଅନ୍ତୁ।"
        )

    # 2. ORANGE ALERT EVALUATION
    elif max_wind >= 45.0 or max_rain >= 35.5 or (weather_code in [95, 96] and max_wind >= 40.0):
        level = "ORANGE"
        title_en = "ORANGE ALERT (Be Prepared / Severe Weather)"
        title_hi = "ऑरेंज अलर्ट (तैयार रहें / गंभीर मौसम)"
        title_or = "ଅରେଞ୍ଜ ଆଲର୍ଟ (ସମ୍ପୂର୍ଣ୍ଣ ପ୍ରସ୍ତୁତ ରୁହନ୍ତୁ / ଭୀଷଣ ପାଣିପାଗ)"
        color = "#ea580c"
        bg_color = "rgba(249, 115, 22, 0.15)"
        border_color = "#c2410c"
        badge_text = "HIGH ALERT / BE PREPARED"
        hazard_type = "Squall Line, Gusty Gales & Heavy Downpour"
        instructions_en = (
            "Significant risk to life and property. Secure loose rooftop structures, prepare emergency disaster kits "
            "(potable water, torch, medical kit), and avoid non-essential travel."
        )
        instructions_hi = (
            "जीवन एवं संपत्ति के लिए बड़ा ख़तरा। आपातकालीन किट तैयार रखें, गैर-जरूरी यात्रा से बचें "
            "और मजबूत पक्के भवनों में सुरक्षित रहें।"
        )
        instructions_or = (
            "ଧନଜୀବନ ପ୍ରତି ବିପଦର ସମ୍ଭାବନା। ଜରୁରୀକାଳୀନ ରିଲିଫ୍ ସାମଗ୍ରୀ ପ୍ରସ୍ତୁତ ରଖନ୍ତୁ ଏବଂ "
            "ଅନାବଶ୍ୟକ ଯାତ୍ରା ସମ୍ପୂର୍ଣ୍ଣ ବନ୍ଦ କରନ୍ତୁ।"
        )

    # 3. YELLOW ALERT EVALUATION
    elif temp >= 40.0 or max_rain >= 15.5 or max_wind >= 30.0 or weather_code in [95, 96, 99]:
        level = "YELLOW"
        title_en = "YELLOW ALERT (Be Updated / Moderate Risk)"
        title_hi = "येलो अलर्ट (सतर्क रहें / जानकारी रखें)"
        title_or = "ୟେଲୋ ସତର୍କତା (ସଜାଗ ରୁହନ୍ତୁ / ନଜର ରଖନ୍ତୁ)"
        color = "#d97706"
        bg_color = "rgba(245, 158, 11, 0.15)"
        border_color = "#b45309"
        badge_text = "WATCH / BE UPDATED"
        hazard_type = (
            "Severe Heatwave Stress (>40°C)"
            if temp >= 40.0
            else "Moderate Thunderstorm, Rain & Localized Wind Gusts"
        )
        instructions_en = (
            "Weather conditions may deteriorate. Track official IMD weather bulletins. "
            "Farmers, coastal workers, and commuters should exercise vigilance."
        )
        instructions_hi = (
            "मौसम की स्थिति बिगड़ सकती है। मौसम विभाग (IMD) की नियमित चेतावनियों पर नज़र रखें। "
            "खुले स्थानों और पेड़ों के नीचे शरण न लें।"
        )
        instructions_or = (
            "ପାଣିପାଗ ଖରାପ ହେବାର ସମ୍ଭାବନା ଅଛି। ପ୍ରଶାସନିକ ସୂଚନା ଉପରେ ନଜର ରଖନ୍ତୁ ଏବଂ "
            "ସତର୍କତା ଅବଲମ୍ବନ କରନ୍ତୁ।"
        )

    # 4. GREEN NORMAL EVALUATION
    else:
        level = "GREEN"
        title_en = "GREEN ALERT (Normal Weather / No Warning)"
        title_hi = "ग्रीन अलर्ट (सामान्य मौसम / कोई चेतावनी नहीं)"
        title_or = "ଗ୍ରୀନ୍ ସୂଚନା (ସ୍ୱାଭାବିକ ପାଣିପାଗ / କୌଣସି ବିପଦ ନାହିଁ)"
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
        instructions_or = (
            "କୌଣସି ପ୍ରତିକୂଳ ଚେତାବନୀ ନାହିଁ। କୃଷି, ଯାତାୟାତ ଏବଂ ଦୈନନ୍ଦିନ କାର୍ଯ୍ୟ ସୁରୁଖୁରୁରେ ଜାରି ରଖିପାରିବେ।"
        )

    return {
        "level": level,
        "title_en": title_en,
        "title_hi": title_hi,
        "title_or": title_or,
        "color": color,
        "bg_color": bg_color,
        "border_color": border_color,
        "badge_text": badge_text,
        "hazard_type": hazard_type,
        "instructions_en": instructions_en,
        "instructions_hi": instructions_hi,
        "instructions_or": instructions_or,
        "wind_trigger_val": round(max_wind, 1),
        "rain_trigger_val": round(max_rain, 1)
    }


def compute_agro_advisory(
    wind_speed: float,
    precipitation: float,
    humidity: float,
    temp: float,
    weather_code: int
) -> Dict[str, Any]:
    """
    Agro-Meteorological Directive Engine (GKMS / ICAR / IMD Protocols):
    - Spraying Safety: Wind < 15 km/h & Rain <= 0.5 mm
    - Irrigation Management: Suspend on Rain >= 10 mm; Micro-irrigate on Temp >= 38°C
    - Harvesting: Expedite if Rain > 15 mm or Wind > 35 km/h
    """
    # 1. Chemical Spraying Window Evaluation
    if wind_speed > 15.0 and precipitation > 0.5:
        spraying_status = "UNSAFE"
        spraying_color = "#ef4444"
        spraying_desc_en = f"Unsafe Window (Wind: {wind_speed:.1f} km/h, Rain: {precipitation:.1f} mm) — High chemical drift and wash-off risk."
        spraying_desc_hi = f"असुरक्षित (हवा: {wind_speed:.1f} km/h, वर्षा: {precipitation:.1f} mm) — कीटनाशक बहने एवं बिखरने का भारी जोखिम।"
        spraying_desc_or = f"ଅନୁପଯୁକ୍ତ (ପବନ: {wind_speed:.1f} km/h, ବର୍ଷା: {precipitation:.1f} mm) — ଔଷଧ ଧୋଇଯିବା ଓ ଉଡ଼ିଯିବାର ଆଶଙ୍କା।"
    elif wind_speed > 15.0:
        spraying_status = "CAUTION"
        spraying_color = "#f59e0b"
        spraying_desc_en = f"Caution (Wind: {wind_speed:.1f} km/h > 15 km/h limit) — Spray drift risk; postpone foliar pesticide applications."
        spraying_desc_hi = f"सावधानी (हवा: {wind_speed:.1f} km/h > 15 km/h) — कीटनाशक हवा में उड़ने का ख़तरा; छिड़काव स्थगित रखें।"
        spraying_desc_or = f"ସତର୍କତା (ପବନ ବେଗ {wind_speed:.1f} km/h > 15 km/h) — କୀଟନାଶକ ଉଡ଼ିଯିବା ଆଶଙ୍କା; ସ୍ପ୍ରେ ସ୍ଥଗିତ ରଖନ୍ତୁ।"
    elif precipitation > 0.5:
        spraying_status = "UNSAFE"
        spraying_color = "#ef4444"
        spraying_desc_en = f"Unsafe (Rain: {precipitation:.1f} mm) — Chemical wash-off risk; postpone all agrochemical spraying."
        spraying_desc_hi = f"असुरक्षित (वर्षा: {precipitation:.1f} mm) — कीटनाशक धुलने का ख़तरा; सभी छिड़काव रोकें।"
        spraying_desc_or = f"ଅନୁପଯୁକ୍ତ (ବର୍ଷା {precipitation:.1f} mm) — ରାସାୟନିକ ଔଷଧ ଧୋଇଯିବା ଆଶଙ୍କା; ସ୍ପ୍ରେ ବନ୍ଦ ରଖନ୍ତୁ।"
    else:
        spraying_status = "OPTIMAL"
        spraying_color = "#10b981"
        spraying_desc_en = f"Optimal Window (Wind: {wind_speed:.1f} km/h, Dry canopy) — Ideal conditions for foliar nutrients and pest control."
        spraying_desc_hi = f"उत्तम समय (शांत हवा {wind_speed:.1f} km/h, सूखा मौसम) — कीटनाशक एवं पोषण छिड़काव के लिए अनुकूल समय।"
        spraying_desc_or = f"ଉତ୍କୃଷ୍ଟ ସମୟ (ଅନୁକୂଳ ପବନ {wind_speed:.1f} km/h, ଶୁଖିଲା ପାଗ) — ଔଷଧ ଓ ସାର ପ୍ରୟୋଗ ପାଇଁ ସର୍ବୋତ୍ତମ ସମୟ।"

    # 2. Irrigation Directive
    if precipitation >= 10.0:
        irrigation_en = "Suspend field irrigation immediately. Ensure proper drainage channels to prevent root hypoxia and waterlogging."
        irrigation_hi = "सिंचाई तुरंत रोकें। खेतों से अतिरिक्त जल निकासी की व्यवस्था करें ताकि फसलों में जलभराव न हो।"
        irrigation_or = "ଜଳସେଚନ ସମ୍ପୂର୍ଣ୍ଣ ବନ୍ଦ ରଖନ୍ତୁ। ଜମିରୁ ଅତିରିକ୍ତ ପାଣି ନିଷ୍କାସନ ପାଇଁ ନାଳି ପ୍ରସ୍ତୁତ ରଖନ୍ତୁ।"
    elif temp >= 38.0:
        irrigation_en = "Elevated evapotranspiration demand. Apply light micro-irrigation during early morning or late dusk hours."
        irrigation_hi = "तीव्र वाष्पीकरण। सुबह जल्दी या शाम के समय हल्की एवं निरंतर सिंचाई करें।"
        irrigation_or = "ପ୍ରଚଣ୍ଡ ଖରା ହେତୁ ସକାଳେ କିମ୍ବା ସନ୍ଧ୍ୟା ସମୟରେ ହାଲୁକା ଜଳସେଚନ କରନ୍ତୁ।"
    else:
        irrigation_en = "Adequate soil moisture status. Maintain standard crop irrigation intervals."
        irrigation_hi = "सामान्य नमी स्तर। फसल की आवश्यकतानुसार नियमित अंतराल पर सिंचाई जारी रखें।"
        irrigation_or = "ମାଟିରେ ସ୍ୱାଭାବିକ ଆର୍ଦ୍ରତା ରହିଛି। ଆବଶ୍ୟକତା ଅନୁଯାୟୀ ନିୟମିତ ଜଳସେଚନ କରନ୍ତୁ।"

    # 3. Harvesting & Produce Protection
    if precipitation > 15.0 or wind_speed > 35.0:
        harvesting_en = "Harvest mature standing crops immediately and move grain to elevated, waterproof covered storage."
        harvesting_hi = "पकी फसलों की तुरंत कटाई करें और अनाज को सुरक्षित, ऊँचे एवं ढके हुए गोदाम में रखें।"
        harvesting_or = "ପାଚିଲା ଧାନ/ଫସଲ ଶୀଘ୍ର କାଟି ନିଅନ୍ତୁ ଏବଂ ସୁରକ୍ଷିତ ଘୋଡ଼ଣୀ ତଳେ ରଖନ୍ତୁ।"
    else:
        harvesting_en = "Atmospheric conditions favorable for harvesting, threshing, sun-drying, and storage."
        harvesting_hi = "फसल कटाई, मड़ाई एवं धूप में सुखाने के लिए मौसम पूरी तरह अनुकूल है।"
        harvesting_or = "ଫସଲ ଅମଳ, ଝାଡ଼ିବା ଏବଂ ଖରାରେ ଶୁଖାଇବା ପାଇଁ ପାଗ ଅନୁକୂଳ ଅଛି।"

    return {
        "spraying_status": spraying_status,
        "spraying_color": spraying_color,
        "spraying_desc_en": spraying_desc_en,
        "spraying_desc_hi": spraying_desc_hi,
        "spraying_desc_or": spraying_desc_or,
        "irrigation_en": irrigation_en,
        "irrigation_hi": irrigation_hi,
        "irrigation_or": irrigation_or,
        "harvesting_en": harvesting_en,
        "harvesting_hi": harvesting_hi,
        "harvesting_or": harvesting_or
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

    if max_wind >= 62.0:
        status = "CRITICAL HAZARD"
        sea_state_en = f"Very Rough to Phenomenal Sea (Squalls >= 62 km/h, Recorded: {max_wind:.1f} km/h)"
        sea_state_hi = f"अत्यंत अशांत एवं प्रचंड समुद्र (हवा >= 62 km/h, दर्ज: {max_wind:.1f} km/h)"
        sea_state_or = f"ଅତ୍ୟନ୍ତ ଅଶାନ୍ତ ଓ ଉତ୍ତାଳ ସମୁଦ୍ର (ପବନ >= 62 km/h, ମାପ: {max_wind:.1f} km/h)"
        color = "#ef4444"
        venture_safe = False
        advisory_en = "TOTAL BAN ON SEA VENTURING. Fishermen are strictly advised NOT to venture into deep sea or coastal waters. Secure all mechanized boats ashore."
        advisory_hi = "समुद्र में जाने पर पूर्ण प्रतिबंध! मछुआरे गहरे समुद्र या तट के पास कतई न जाएँ। नावों को सुरक्षित स्थानों पर बाँधें।"
        advisory_or = "ସମୁଦ୍ରକୁ ଯିବା ଉପରେ ସମ୍ପୂର୍ଣ୍ଣ କଟକଣା! ମତ୍ସ୍ୟଜୀବୀମାନେ ଗଭୀର ସମୁଦ୍ର କିମ୍ବା ଉପକୂଳକୁ ଯାଆନ୍ତୁ ନାହିଁ। ଡଙ୍ଗାଗୁଡ଼ିକୁ ସୁରକ୍ଷିତ ବାନ୍ଧି ରଖନ୍ତୁ।"
    elif max_wind >= 45.0:
        status = "WARNING"
        sea_state_en = f"Rough to Very Rough Sea (Wind: {max_wind:.1f} km/h)"
        sea_state_hi = f"अशांत समुद्र (हवा: {max_wind:.1f} km/h)"
        sea_state_or = f"ଅଶାନ୍ତ ସମୁଦ୍ର (ପବନ ବେଗ {max_wind:.1f} km/h)"
        color = "#f97316"
        venture_safe = False
        advisory_en = "HIGH RISK. Fishermen in deep sea are advised to return to harbor immediately. Artisanal and non-mechanized craft operations suspended."
        advisory_hi = "उच्च जोखिम। गहरे समुद्र में गए मछुआरे तत्काल तट पर लौट आएँ। छोटी नावों का परिचालन स्थगित रखें।"
        advisory_or = "ଉଚ୍ଚ ବିପଦ। ସମୁଦ୍ର ମଧ୍ୟରେ ଥିବା ମତ୍ସ୍ୟଜୀବୀମାନେ ତୁରନ୍ତ ଉପକୂଳକୁ ଫେରିଆସନ୍ତୁ। ଛୋଟ ଡଙ୍ଗା ଚଳାଚଳ ବନ୍ଦ ରଖନ୍ତୁ।"
    elif max_wind >= 30.0:
        status = "CAUTION"
        sea_state_en = f"Moderate to Squally Conditions (Wind: {max_wind:.1f} km/h)"
        sea_state_hi = f"मध्यम से तेज समुद्री हवाएँ ({max_wind:.1f} km/h)"
        sea_state_or = f"ମଧ୍ୟମ ଧରଣର ଉତ୍ତାଳ ସମୁଦ୍ର ({max_wind:.1f} km/h)"
        color = "#eab308"
        venture_safe = True
        advisory_en = "EXERCISE CAUTION. Artisanal boat operators should stay close to coastline and avoid venturing into deep sea."
        advisory_hi = "सतर्कता बरतें। छोटी नाव चालक गहरे समुद्र में जाने से बचें एवं तट के निकट ही रहें।"
        advisory_or = "ସତର୍କତା ଅବଲମ୍ବନ କରନ୍ତୁ। ଛୋଟ ଡଙ୍ଗା ଚାଳକମାନେ ଗଭୀର ସମୁଦ୍ରକୁ ନଯାଇ ଉପକୂଳ ନିକଟରେ ରୁହନ୍ତୁ।"
    else:
        status = "SAFE"
        sea_state_en = f"Smooth to Slight Sea (Wind: {max_wind:.1f} km/h)"
        sea_state_hi = f"शांत एवं अनुकूल समुद्र (हवा: {max_wind:.1f} km/h)"
        sea_state_or = f"ଶାନ୍ତ ଓ ଅନୁକୂଳ ସମୁଦ୍ର (ପବନ ବେଗ {max_wind:.1f} km/h)"
        color = "#10b981"
        venture_safe = True
        advisory_en = "SAFE FOR FISHING. Sea conditions are calm and favorable for routine coastal and deep-sea operations."
        advisory_hi = "मत्स्य पालन हेतु सुरक्षित। समुद्र शांत है एवं सामान्य मछली पकड़ने के लिए स्थिति अनुकूल है।"
        advisory_or = "ମାଛ ଧରିବା ପାଇଁ ସୁରକ୍ଷିତ। ସମୁଦ୍ର ଶାନ୍ତ ରହିଛି ଏବଂ ସ୍ୱାଭାବିକ ମାଛ ଧରା କାର୍ଯ୍ୟ ଜାରି ରଖିପାରିବେ।"

    return {
        "status": status,
        "sea_state_en": sea_state_en,
        "sea_state_hi": sea_state_hi,
        "sea_state_or": sea_state_or,
        "color": color,
        "venture_safe": venture_safe,
        "advisory_en": advisory_en,
        "advisory_hi": advisory_hi,
        "advisory_or": advisory_or,
        "is_coastal_region": is_coastal
    }
