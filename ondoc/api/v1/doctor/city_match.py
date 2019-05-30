def city_match(city):
    if isinstance(city, str) and city.lower() in ('bengaluru', 'bengalooru'):
        city = 'bangalore'
    elif isinstance(city, str) and city.lower() in ('gurugram', 'gurugram rural'):
        city = 'gurgaon'
    else:
        city = city

    return city
