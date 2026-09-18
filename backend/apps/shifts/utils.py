"""Shared shift/day helpers used by planning and restrictions.

Canonical source of truth: the Shift model and shift_days.WEEKDAY_CHOICES.
No per-call caching here on purpose: callers that need caching wrap these
(planning uses thread-local _get_gen_cache; restrictions uses module _cache).
"""
from apps.shifts.models import Shift
from apps.shift_days.models import WEEKDAY_CHOICES


def load_shift_slots():
    """Root shift slot definitions from the Shift model (dict form).

    Returns list of {'code': str(id), 'label': name,
    'attributes': {'start_time','end_time'}} ordered by id.
    """
    return [
        {
            'code': str(s.id),
            'label': s.name,
            'attributes': {
                'start_time': s.start_time.strftime('%H:%M') if s.start_time else '00:00',
                'end_time': s.end_time.strftime('%H:%M') if s.end_time else '00:00',
            },
        }
        for s in Shift.objects.order_by('id')
    ]


def shift_codes():
    """Shift codes (str ids) ordered by id. Equivalent to
    [slot['code'] for slot in load_shift_slots()] but without building dicts.
    """
    return [str(s.id) for s in Shift.objects.order_by('id')]


def day_names():
    """Day-of-week labels from WEEKDAY_CHOICES (Lunes..Domingo, with accents)."""
    return [label for _, label in WEEKDAY_CHOICES]
