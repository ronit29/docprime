# Generated by Django 2.0.5 on 2019-03-04 07:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0082_userprofile_whatsapp_optin'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='whatsapp_is_declined',
            field=models.BooleanField(default=False),
        ),
    ]
