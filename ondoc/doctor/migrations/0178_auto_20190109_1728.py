# Generated by Django 2.0.5 on 2019-01-09 11:58

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('doctor', '0177_merge_20190108_1624'),
    ]

    operations = [
        migrations.RenameField(
            model_name='hospital',
            old_name='pyhsical_aggrement_signed',
            new_name='physical_agreement_signed',
        ),
        migrations.AddField(
            model_name='doctor',
            name='disable_comments',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='doctor',
            name='disable_reason',
            field=models.PositiveIntegerField(blank=True, choices=[('', 'Select'), (1, 'Doctor not associated with the hospital anymore'), (2, 'Doctor only for IPD services'), (3, 'Doctor available only On-Call'), (4, 'Incorrect contact details'), (5, 'MoU agreement needed'), (6, 'Doctor not interested for tie-up'), (7, 'Issue in discount % / consultation charges'), (9, 'Others')], null=True),
        ),
        migrations.AddField(
            model_name='doctor',
            name='disabled_after',
            field=models.PositiveIntegerField(blank=True, choices=[('', 'Select'), (1, 'Welcome Calling'), (2, 'Escalation')], null=True),
        ),
        migrations.AddField(
            model_name='doctor',
            name='disabled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='doctor',
            name='disabled_by',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='disabled_doctors', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='hospital',
            name='disable_comments',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='hospital',
            name='disable_reason',
            field=models.PositiveIntegerField(blank=True, choices=[('', 'Select'), (1, 'Incorrect contact details'), (2, 'MoU agreement needed'), (3, 'Hospital not interested for tie-up'), (4, 'Issue in discount % / consultation charges'), (9, 'Others')], null=True),
        ),
        migrations.AddField(
            model_name='hospital',
            name='disabled_after',
            field=models.PositiveIntegerField(blank=True, choices=[('', 'Select'), (1, 'Welcome Calling'), (2, 'Escalation')], null=True),
        ),
        migrations.AddField(
            model_name='hospital',
            name='disabled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hospital',
            name='disabled_by',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='disabled_hospitals', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='hospital',
            name='physical_agreement_signed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hospital',
            name='welcome_calling_done',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='hospital',
            name='welcome_calling_done_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
