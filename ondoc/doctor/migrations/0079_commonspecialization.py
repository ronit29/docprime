# Generated by Django 2.0.5 on 2018-07-20 09:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0078_auto_20180720_1436'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommonSpecialization',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('specialization', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='common_specialization', to='doctor.Specialization')),
            ],
            options={
                'db_table': 'common_specializations',
            },
        ),
    ]
