# Generated by Django 2.0.5 on 2019-01-17 11:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0049_auto_20190111_1526'),
    ]

    operations = [
        migrations.AddField(
            model_name='merchantpayout',
            name='amount_paid',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='merchantpayout',
            name='type',
            field=models.PositiveIntegerField(choices=[(1, 'Automatic'), (2, 'Manual')], default=1),
        ),
        migrations.AddField(
            model_name='merchantpayout',
            name='utr_no',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
