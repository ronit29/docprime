# Generated by Django 2.0.5 on 2019-06-10 09:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0206_labappointment_status_change_comments'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='deleted',
            field=models.DateTimeField(editable=False, null=True),
        ),
    ]
