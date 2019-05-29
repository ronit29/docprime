
def city_match(city):
    if not city:
        return city
    if city.lower() in ('bengaluru', 'bengalooru'):
        city = 'bangalore'
    elif city.lower() in ('gurugram', 'gurugram rural'):
        city = 'gurgaon'
    else:
        city = city

    return city