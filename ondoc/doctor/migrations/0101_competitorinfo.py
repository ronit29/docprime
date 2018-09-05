# Generated by Django 2.0.5 on 2018-09-04 07:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0100_doctorclinictiming_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompetitorInfo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.PositiveSmallIntegerField(blank=True, choices=[('', 'Select'), (1, 'PRACTO'), (2, 'LYBRATE')], null=True)),
                ('hospital_name', models.CharField(max_length=200)),
                ('fee', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('url', models.URLField()),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
