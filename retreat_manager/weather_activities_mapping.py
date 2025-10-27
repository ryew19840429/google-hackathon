mapping = [ 
    {"temp": "Hot", "rain": "Dry", "activities": ["Outdoor sports", "Barbecue", "Music festival"]},
    {"temp": "Hot", "rain": "Rainy", "activities": ["Indoor exhibition", "Cinema", "Indoor gym", "Coffee meetup"]},
    {"temp": "Mild", "rain": "Dry", "activities": ["Park activities", "Team building", "Outdoor workshop"]},
    {"temp": "Mild", "rain": "Rainy", "activities": ["Indoor workshop", "Small conference", "Indoor recreation"]},
    {"temp": "Cold", "rain": "Dry", "activities": ["Indoor meeting", "Training session", "Museum visit", "Greenhouse event"]},
    {"temp": "Cold", "rain": "Rainy", "activities": ["Online webinar", "Remote event", "Home interactive game"]}
]

def classify_temp(temp_c):
    if temp_c > 25:
        return "Hot"
    elif temp_c > 10:
        return "Mild"
    else:
        return "Cold"

def classify_rain(rain_mm):
    if rain_mm < 1:
        return "Dry"
    else:
        return "Rainy"

def recommend_activities(temp_c, rain_mm):
    t = classify_temp(temp_c)
    r = classify_rain(rain_mm)
    for entry in mapping:
        if entry["temp"] == t and entry["rain"] == r:
            return entry["activities"]
    return []

# Example
print(recommend_activities(28, 0.2))  # Hot + Dry → Outdoor sports, Barbecue, Music festival
