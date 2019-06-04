# Generated by Django 2.0.5 on 2019-05-15 12:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0029_auto_20190515_1323'),
    ]

    operations = [
        migrations.AddField(
            model_name='banner',
            name='insurance_check',
            field=models.CharField(choices=[('insured', 'Insured User'), ('non_insured', 'Non Insured'), ('all', 'All')], default='all', max_length=100),
        ),
        migrations.AddField(
            model_name='banner',
            name='show_to_users',
            field=models.CharField(choices=[('logged_in', 'Logged In'), ('logged_out', 'Logged Out'), ('all', 'All')], default='all', max_length=100),
        ),
    ]