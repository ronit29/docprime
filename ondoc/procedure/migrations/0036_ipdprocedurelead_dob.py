# Generated by Django 2.0.5 on 2019-04-17 12:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0035_ipdprocedure_show_about'),
    ]

    operations = [
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='dob',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
