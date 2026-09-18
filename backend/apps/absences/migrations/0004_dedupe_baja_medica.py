"""
Data migration: elimina el tipo de ausencia duplicado "Baja medica" (sin tilde),
conservando "Baja médica" (con tilde).

Tarea "[BE] Eliminar el tipo de ausencia 'Baja medica' duplicado".
- AC-1: en el desplegable solo queda "Baja médica" (con tilde).
- AC-2: las ausencias que apuntaran al sin-tilde se REASIGNAN al con-tilde antes
  de borrar (AbsenceRequest.type es FK on_delete=PROTECT → borrar con requests
  asociadas fallaría; por eso reasignamos primero).
- AC-3: el resto de tipos no se tocan.

Idempotente: si el sin-tilde ya no existe, no hace nada. Robusto: si faltara el
con-tilde, lo crea antes de reasignar.
"""
from django.db import migrations

WRONG = 'Baja medica'    # sin tilde (a eliminar)
RIGHT = 'Baja médica'    # con tilde (a conservar)


def dedupe(apps, schema_editor):
    AbsenceType = apps.get_model('absences', 'AbsenceType')
    AbsenceRequest = apps.get_model('absences', 'AbsenceRequest')

    wrong = AbsenceType.objects.filter(name=WRONG).first()
    if not wrong:
        return  # ya limpio, nada que hacer

    # Asegurar el tipo correcto (con tilde). Si no existiese, se crea para no
    # perder las ausencias del sin-tilde.
    right = AbsenceType.objects.filter(name=RIGHT).first()
    if not right:
        right = AbsenceType.objects.create(
            name=RIGHT,
            requires_approval=wrong.requires_approval,
            active=wrong.active,
        )

    # Reasignar todas las ausencias del sin-tilde al con-tilde (AC-2).
    AbsenceRequest.objects.filter(type=wrong).update(type=right)

    # Ahora el sin-tilde no tiene requests → se puede borrar (PROTECT no salta).
    wrong.delete()


def undo(apps, schema_editor):
    # Reversa best-effort: recrea el tipo sin-tilde (vacío). No se pueden
    # des-reasignar las ausencias (no guardamos cuáles eran); quedan en el
    # con-tilde, que es lo correcto.
    AbsenceType = apps.get_model('absences', 'AbsenceType')
    AbsenceType.objects.get_or_create(name=WRONG, defaults={'active': True})


class Migration(migrations.Migration):

    dependencies = [
        ('absences', '0003_absencerequest_indefinite_and_more'),
    ]

    operations = [
        migrations.RunPython(dedupe, undo),
    ]
