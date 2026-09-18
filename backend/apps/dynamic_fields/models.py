from django.db import models


class EntityType(models.Model):
    """
    Defines a dynamic entity type (e.g. 'store', 'zone', 'vehicle').
    System entities (role, shift) are marked is_system=True and cannot be deleted.
    Each entity type gets its own CRUD page in the sidebar.
    """
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default='category')
    order = models.IntegerField(default=0)
    show_in_sidebar = models.BooleanField(default=True)
    is_system = models.BooleanField(
        default=False,
        help_text='System entities cannot be deleted and are always present in the sidebar',
    )
    display_field = models.CharField(
        max_length=50,
        default='name',
        help_text='Clave del campo de data que se usa como etiqueta en selectores y tablas (ej: name, nombre, codigo)',
    )
    use_as_filter = models.BooleanField(
        default=False,
        help_text='Si es True, esta entidad aparece como filtro en el dashboard',
    )
    is_planning_scope = models.BooleanField(
        default=False,
        help_text='Si es True, los registros de esta entidad son el "ámbito" de la planificación (turno + entidad). Solo una entidad debería tenerlo activo.',
    )
    show_in_schedule = models.BooleanField(
        default=False,
        help_text='Si es True, los registros de esta entidad aparecen como pills asignables dentro de cada asignación del horario (ej: roles, secciones). Independiente del ámbito de planificación.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Tipo de entidad'
        verbose_name_plural = 'Tipos de entidad'

    def __str__(self):
        return self.name


class EntityRecord(models.Model):
    """A single record belonging to a dynamic entity type."""
    entity_type = models.ForeignKey(
        EntityType, on_delete=models.CASCADE,
        related_name='records', to_field='slug',
    )
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Registro de entidad'
        verbose_name_plural = 'Registros de entidad'

    def __str__(self):
        label = self.data.get('name') or self.data.get('label') or f'#{self.id}'
        return f'{self.entity_type_id} / {label}'


class EntityField(models.Model):
    FIELD_TYPES = [
        ('text', 'Texto'),
        ('number', 'Numero'),
        # Decimal. Necesario para las horas semanales por contrato: 37,5 horas no
        # se puede representar con 'number' (entero) y redondear falsea la
        # planificacion. El valor se guarda en el JSON de custom_data como float
        # nativo, asi que no hay precision/escala que migrar mas adelante.
        ('float', 'Decimal'),
        ('boolean', 'Si/No'),
        ('color', 'Color'),
        ('time', 'Hora'),
        ('select', 'Seleccion'),
        ('textarea', 'Texto largo'),
        ('catalog_select', 'Seleccion de catalogo'),
        ('multi_catalog_select', 'Seleccion multiple de catalogo'),
        ('entity_select', 'Seleccion de entidad'),
        ('multi_entity_select', 'Seleccion multiple de entidad'),
        ('icon', 'Icono'),
    ]

    entity_type = models.CharField(max_length=50)  # references EntityType.slug
    key = models.SlugField(max_length=50)
    label = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    required = models.BooleanField(default=False)
    default_value = models.CharField(max_length=200, blank=True)
    placeholder = models.CharField(max_length=100, blank=True)
    options = models.JSONField(
        default=list,
        blank=True,
        help_text='Opciones para campo tipo select: ["opcion1", "opcion2"]',
    )
    kind_code = models.CharField(
        max_length=50,
        blank=True,
        help_text='Codigo del Kind del catalogo para campos catalog_select / multi_catalog_select',
    )
    target_entity = models.CharField(
        max_length=50,
        blank=True,
        help_text='Slug del EntityType relacionado para campos entity_select / multi_entity_select',
    )
    display_key = models.CharField(
        max_length=50,
        blank=True,
        help_text='Campo del entity relacionado a mostrar en la tabla (si vacio, usa display_field del EntityType)',
    )
    depends_on = models.CharField(
        max_length=50,
        blank=True,
        help_text='Clave del campo del que depende (en la misma entidad). Filtra las opciones automaticamente.',
    )
    depends_on_field = models.CharField(
        max_length=50,
        blank=True,
        help_text='Clave en el data del target_entity que debe coincidir con el valor del campo depends_on.',
    )
    visible_when_field = models.CharField(
        max_length=50,
        blank=True,
        help_text='Clave del campo (misma entidad) que controla la visibilidad de este campo.',
    )
    visible_when_value = models.CharField(
        max_length=200,
        blank=True,
        help_text='Valor que debe tener visible_when_field para que este campo sea visible. Para boolean usar "true"/"false".',
    )
    show_in_list = models.BooleanField(
        default=False,
        help_text='Mostrar como columna en la tabla del cliente',
    )
    show_as_filter = models.BooleanField(
        default=False,
        help_text='Mostrar como desplegable de filtro en la vista de registros',
    )
    allow_unassigned_filter = models.BooleanField(
        default=False,
        help_text='Anade la opcion "Sin asignar" al filtro de este campo, para '
                  'localizar los registros que no tienen ningun valor. Es por '
                  'campo, no global.',
    )
    allow_priority = models.BooleanField(
        default=False,
        help_text='Permite asignar prioridad/preferencia a cada seleccion (para campos multi-seleccion)',
    )
    help_text = models.CharField(
        max_length=300,
        blank=True,
        help_text='Texto de ayuda mostrado al usuario bajo el campo',
    )
    order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['entity_type', 'key']
        ordering = ['entity_type', 'order', 'label']
        verbose_name = 'Campo dinamico'
        verbose_name_plural = 'Campos dinamicos'

    def __str__(self):
        return f'{self.entity_type} → {self.label}'
