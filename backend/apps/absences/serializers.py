from rest_framework import serializers

from apps.dynamic_fields.mixins import DynamicFieldsMixin
from .models import AbsenceType, AbsenceRequest


class AbsenceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbsenceType
        fields = ['id', 'name', 'requires_approval', 'active']


def _sin_acentos(texto):
    """minusculas y sin tildes, para comparar nombres de tipos."""
    import unicodedata
    plano = unicodedata.normalize('NFD', str(texto or '').strip().lower())
    return ''.join(c for c in plano if unicodedata.category(c) != 'Mn')


def resolver_absence_type(label):
    """Devuelve el AbsenceType que corresponde a un valor del catalogo.

    El catalogo (Kind 'absence_type') es la fuente de verdad de que tipos
    existen: es lo que el cliente gestiona desde AdminZebra. Pero la ausencia
    guarda una FK a AbsenceType, y las 29 ausencias ya registradas apuntan ahi,
    asi que la tabla se mantiene y se sincroniza por nombre: si el cliente crea
    "Excedencia" en el catalogo, la primera ausencia de ese tipo crea su fila.

    Asi el historico no se toca y el cliente sigue anadiendo tipos sin
    desarrollo.
    """
    if not label:
        return None

    limpio = str(label).strip()
    if not limpio:
        return None

    # Coincidencia exacta primero (ignorando mayusculas).
    tipo = AbsenceType.objects.filter(name__iexact=limpio).first()
    if tipo:
        return tipo

    # Sin acentos: al importar por Excel la gente escribe "Baja medica" y no
    # debe crearse un tipo aparte de "Baja medica" con acento. Se compara en
    # Python porque la BD no tiene collation sin acentos garantizada.
    objetivo = _sin_acentos(limpio)
    for t in AbsenceType.objects.all():
        if _sin_acentos(t.name) == objetivo:
            return t

    return AbsenceType.objects.create(name=limpio)


class AbsenceRequestSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    """Ausencia con campos configurables desde AdminZebra (AC-1/AC-2).

    El mixin anade `custom_data` + `field_schema` igual que en Worker, asi que
    el formulario y las columnas de la tabla se construyen desde la
    configuracion en vez de estar fijos en el codigo.
    """

    _entity_type = 'absence'

    worker_name = serializers.CharField(source='worker.name', read_only=True)
    type_name = serializers.CharField(source='type.name', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AbsenceRequest
        fields = [
            'id', 'worker', 'worker_name', 'type', 'type_name',
            'start_date', 'end_date', 'indefinite', 'reason', 'status',
            'reviewed_by', 'reviewed_by_name', 'reviewed_at', 'created_at',
            'custom_data',
        ]
        read_only_fields = ['status', 'reviewed_by', 'reviewed_at']
        # 'type' puede llegar por custom_data['tipo'] (catalogo), asi que no se
        # exige en la peticion; se resuelve en validate().
        extra_kwargs = {'type': {'required': False}}

    def to_representation(self, instance):
        """Rellena custom_data['tipo'] desde la FK cuando esta vacio.

        Las ausencias registradas antes de esta configuracion guardan su tipo
        solo en la FK `type`, asi que su custom_data llega vacio y el
        desplegable del formulario saldria en blanco al editarlas (y el guardado
        fallaria, porque el tipo es obligatorio). Se sincroniza al leer, sin
        tocar los datos guardados.
        """
        data = super().to_representation(instance)
        cd = data.get('custom_data') or {}
        if not cd.get('tipo') and instance.type_id:
            cd['tipo'] = instance.type.name
            data['custom_data'] = cd
        return data

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.email
        return None

    def validate(self, attrs):
        """Reglas de vigencia de la ausencia (AC-2/AC-3):
        - indefinida  → end_date se ignora (se guarda como None), no obligatoria.
        - no indefinida → end_date obligatoria y no anterior a start_date.
        En PATCH parcial se toma el valor entrante o el actual de la instancia.
        """
        # super() = DynamicFieldsMixin.validate (campos obligatorios al crear).
        attrs = super().validate(attrs)

        inst = getattr(self, 'instance', None)

        # El tipo puede venir del catalogo (custom_data['tipo']) o como FK
        # directa (compatibilidad con lo que ya habia). El catalogo manda.
        cd = attrs.get('custom_data') or {}
        etiqueta = cd.get('tipo')
        if etiqueta and not attrs.get('type'):
            tipo = resolver_absence_type(etiqueta)
            if tipo:
                attrs['type'] = tipo
        if not attrs.get('type') and inst is None:
            raise serializers.ValidationError({
                'type': 'El tipo de ausencia es obligatorio.'})

        indefinite = attrs.get('indefinite', getattr(inst, 'indefinite', False))
        start = attrs.get('start_date', getattr(inst, 'start_date', None))
        end = attrs.get('end_date', getattr(inst, 'end_date', None))

        if indefinite:
            # Una ausencia indefinida no lleva fecha de fin: la limpiamos.
            attrs['end_date'] = None
        else:
            if end is None:
                raise serializers.ValidationError({
                    'end_date': 'La fecha de fin es obligatoria salvo que la ausencia sea indefinida.',
                })
            if start is not None and end < start:
                raise serializers.ValidationError({
                    'end_date': 'La fecha de fin no puede ser anterior a la de inicio.',
                })
        return attrs
