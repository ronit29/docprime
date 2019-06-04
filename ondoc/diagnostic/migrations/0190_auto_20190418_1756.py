# Generated by Django 2.0.5 on 2019-04-18 12:26

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('diagnostic', '0189_merge_20190412_2013'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='disable_comments',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='lab',
            name='disable_reason',
            field=models.PositiveIntegerField(blank=True, choices=[('', 'Select'), (1, 'Incorrect contact details'), (2, 'MoU agreement needed'), (3, 'Lab not interested for tie-up'), (4, 'Issue in discount % / charges'), (10, 'Phone ringing but could not connect'), (5, 'Duplicate'), (9, 'Others (please specify)')], null=True),
        ),
        migrations.AddField(
            model_name='lab',
            name='disabled_after',
            field=models.PositiveIntegerField(blank=True, choices=[('', 'Select'), (1, 'Welcome Calling'), (2, 'Escalation')], null=True),
        ),
        migrations.AddField(
            model_name='lab',
            name='disabled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='lab',
            name='disabled_by',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='disabled_lab', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='lab',
            name='welcome_calling_done',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='lab',
            name='welcome_calling_done_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='labappointment',
            name='money_pool',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lab_apps', to='account.MoneyPool'),
        ),
    ]