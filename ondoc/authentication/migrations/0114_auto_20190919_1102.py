# Generated by Django 2.0.5 on 2019-09-19 05:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0113_genericadmin_is_partner_lab_admin'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofileemailupdate',
            name='old_email',
            field=models.CharField(blank=True, max_length=256, null=True),
        ),
    ]
