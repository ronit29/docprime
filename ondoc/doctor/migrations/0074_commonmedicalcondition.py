# Generated by Django 2.0.5 on 2018-07-16 13:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0073_merge_20180712_1912'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommonMedicalCondition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('condition', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='common_condition', to='doctor.MedicalCondition')),
            ],
            options={
                'db_table': 'common_medical_condition',
            },
        ),
    ]
