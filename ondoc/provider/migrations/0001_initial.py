# Generated by Django 2.0.5 on 2019-07-24 08:56

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0108_merge_20190718_1833'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('doctor', '0281_auto_20190719_1121'),
    ]

    operations = [
        migrations.CreateModel(
            name='EConsultation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('fees', models.DecimalField(decimal_places=2, max_digits=10)),
                ('validity', models.PositiveIntegerField(blank=True, null=True)),
                ('payment_status', models.PositiveSmallIntegerField(choices=[(1, 'Payment Accepted'), (0, 'Payment Pending')], default=0)),
                ('link', models.CharField(blank=True, max_length=256, null=True)),
                ('created_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('doctor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='doctor.Doctor')),
                ('offline_patient', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='doctor.OfflinePatients')),
                ('online_patient', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='authentication.UserProfile')),
            ],
            options={
                'db_table': 'e_consultation',
            },
        ),
    ]
