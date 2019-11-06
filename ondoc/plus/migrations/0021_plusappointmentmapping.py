# Generated by Django 2.0.5 on 2019-09-11 12:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('plus', '0020_auto_20190906_1200'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlusAppointmentMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_id', models.PositiveIntegerField()),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='contenttypes.ContentType')),
                ('plus_plan', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='plan_appointment', to='plus.PlusPlans')),
                ('plus_user', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='appointment_mapping', to='plus.PlusUser')),
            ],
            options={
                'db_table': 'plus_appointment_mapping',
            },
        ),
    ]