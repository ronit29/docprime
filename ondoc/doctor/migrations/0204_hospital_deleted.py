# Generated by Django 2.0.5 on 2019-02-25 16:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0203_doctor_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='deleted',
            field=models.DateTimeField(editable=False, null=True),
        ),
    ]