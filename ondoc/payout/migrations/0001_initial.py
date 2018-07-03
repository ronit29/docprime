# Generated by Django 2.0.6 on 2018-06-27 12:56

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Outstanding',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('net_hos_doc_id', models.IntegerField()),
                ('outstanding_level', models.IntegerField(choices=[(0, 'Hospital Network Level'), (1, 'Hospital Level'), (2, 'Doctor Level'), (3, 'Lab Network Level'), (4, 'Lab Level')])),
                ('current_month_outstanding', models.DecimalField(decimal_places=2, max_digits=10)),
                ('previous_month_outstanding', models.DecimalField(decimal_places=2, max_digits=10)),
                ('paid_by_pb', models.DecimalField(decimal_places=2, max_digits=10)),
                ('paid_to_pb', models.DecimalField(decimal_places=2, max_digits=10)),
                ('outstanding_month', models.PositiveSmallIntegerField(max_length=12)),
                ('outstanding_year', models.IntegerField()),
            ],
            options={
                'db_table': 'outstanding',
            },
        ),
        migrations.CreateModel(
            name='Payout',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('net_hos_doc_id', models.IntegerField()),
                ('payout_level', models.PositiveSmallIntegerField(choices=[(0, 'Hospital Network Level'), (1, 'Hospital Level'), (2, 'Doctor Level'), (3, 'Lab Network Level'), (4, 'Lab Level')])),
                ('payment_type', models.PositiveSmallIntegerField(choices=[(0, 'PG'), (1, 'Cash'), (2, 'Cheque')])),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
            ],
            options={
                'db_table': 'payout',
            },
        ),
        migrations.AlterUniqueTogether(
            name='outstanding',
            unique_together={('net_hos_doc_id', 'outstanding_level', 'outstanding_month', 'outstanding_year')},
        ),
        migrations.CreateModel(
            name='DoctorOutstanding',
            fields=[
            ],
            options={
                'indexes': [],
                'proxy': True,
            },
            bases=('payout.outstanding',),
        ),
        migrations.CreateModel(
            name='HospitalOutstanding',
            fields=[
            ],
            options={
                'indexes': [],
                'proxy': True,
            },
            bases=('payout.outstanding',),
        ),
        migrations.CreateModel(
            name='NetworkOutstanding',
            fields=[
            ],
            options={
                'indexes': [],
                'proxy': True,
            },
            bases=('payout.outstanding',),
        ),
    ]