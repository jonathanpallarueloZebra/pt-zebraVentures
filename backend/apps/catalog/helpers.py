from .models import KindValue, KindValueAttribute


def get_values(kind_code, active_only=True):
    """Return values for a Kind with attributes as a dict for easy access."""
    qs = KindValue.objects.filter(kind__code=kind_code).prefetch_related(
        'attributes__attribute'
    )
    if active_only:
        qs = qs.filter(active=True)
    result = []
    for v in qs.order_by('order'):
        attrs = {va.attribute.key: va.value for va in v.attributes.all()}
        result.append({
            'code': v.code,
            'label': v.label,
            'color': v.color,
            'icon': v.icon,
            'attributes': attrs,
        })
    return result


def get_codes(kind_code, active_only=True):
    """Return flat list of codes for a Kind."""
    qs = KindValue.objects.filter(kind__code=kind_code)
    if active_only:
        qs = qs.filter(active=True)
    return list(qs.order_by('order').values_list('code', flat=True))


def get_choices(kind_code, active_only=True):
    """Return Django choices list [(code, label), ...] for a Kind."""
    qs = KindValue.objects.filter(kind__code=kind_code)
    if active_only:
        qs = qs.filter(active=True)
    return list(qs.order_by('order').values_list('code', 'label'))


def get_attribute_value(kind_code, value_code, attr_key, default=None):
    """Get a specific attribute value for a KindValue."""
    try:
        va = KindValueAttribute.objects.select_related('attribute').get(
            kind_value__kind__code=kind_code,
            kind_value__code=value_code,
            attribute__key=attr_key,
        )
        return va.value
    except KindValueAttribute.DoesNotExist:
        return default
