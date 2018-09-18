# Generated by Django 2.0.5 on 2018-09-18 05:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0110_auto_20180914_1654'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompetitorHit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.PositiveSmallIntegerField(choices=[('', 'Select'), (1, 'Practo'), (2, 'Lybrate')])),
                ('hits', models.BigIntegerField()),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='competitor_doctor_hits', to='doctor.Doctor')),
            ],
            options={
                'db_table': 'competitor_hit',
            },
        ),
    ]
