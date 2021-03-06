# Generated by Django 2.0.5 on 2019-01-08 12:17

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0175_opdappointment_price_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchScore',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('popularity_score', models.PositiveIntegerField(default=None, null=True)),
                ('years_of_experience', models.PositiveIntegerField(default=None, null=True)),
                ('doctors_in_clinic', models.PositiveIntegerField(default=None, null=True)),
                ('final_score', models.PositiveIntegerField(default=None, null=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor')),
            ],
            options={
                'db_table': 'search_score',
            },
        ),
    ]
