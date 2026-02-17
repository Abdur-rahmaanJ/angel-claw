@skill
def get_weather(city: str, units: str = 'metric') -> str:
    """Returns a mock weather string for the specified city and units (metric or imperial)."""
    temperature = '20°C' if units == 'metric' else '68°F'
    description = 'Partly cloudy'
    return f"Weather for {city}: {description}, {temperature} ({units} units)"