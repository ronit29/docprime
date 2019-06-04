# Generated by Django 2.0.5 on 2019-03-26 08:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0018_integratorhistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='integratorhistory',
            name='accepted_through',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AlterField(
            model_name='integratorhistory',
            name='status',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Pushed and not accepted, Manage Manually'), (2, 'Pushed and accepted'), (3, 'Not pushed, Manage Manually')], default=3),
        ),
    ]