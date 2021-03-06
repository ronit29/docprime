# Generated by Django 2.0.5 on 2019-11-29 05:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0115_otpverifications_req_count'),
        ('notification', '0068_auto_20191127_1218'),
    ]

    operations = [
        migrations.AddField(
            model_name='ipdintimateemailnotification',
            name='profile',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='ipd_profile', to='authentication.UserProfile'),
        ),
    ]
