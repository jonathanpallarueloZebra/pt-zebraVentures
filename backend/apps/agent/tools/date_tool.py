from datetime import datetime, date


def get_current_date() -> str:
    """Returns the current date in YYYY-MM-DD format."""
    return date.today().isoformat()


def get_current_datetime() -> str:
    """Returns the current date and time in ISO format."""
    return datetime.now().isoformat()


def get_day_of_week() -> str:
    """Returns the current day of the week in Spanish."""
    days = {
        0: 'Lunes', 1: 'Martes', 2: 'Miércoles',
        3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'
    }
    return days[date.today().weekday()]


# Tool definition for the agent
DATE_TOOLS = [
    {
        'name': 'get_current_date',
        'description': 'Obtiene la fecha actual en formato YYYY-MM-DD',
        'function': get_current_date,
    },
    {
        'name': 'get_current_datetime',
        'description': 'Obtiene la fecha y hora actual en formato ISO',
        'function': get_current_datetime,
    },
    {
        'name': 'get_day_of_week',
        'description': 'Obtiene el día de la semana actual en español',
        'function': get_day_of_week,
    },
]
