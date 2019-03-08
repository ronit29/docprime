# Generated by Django 2.0.5 on 2019-03-06 05:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0211_merge_20190304_1959'),
    ]

    operations = [
        migrations.CreateModel(
            name='HospitalHelpline',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('std_code', models.IntegerField(blank=True, null=True)),
                ('number', models.BigIntegerField()),
                ('details', models.CharField(blank=True, max_length=200)),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hospital_helpline_numbers', to='doctor.Hospital')),
            ],
            options={
                'db_table': 'hospital_helpline',
            },
        ),
    ]
