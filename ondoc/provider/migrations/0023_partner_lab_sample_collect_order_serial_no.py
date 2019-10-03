from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0022_auto_20191003_1446'),
    ]

    operations = [
        migrations.RunSQL(
            'ALTER SEQUENCE partner_lab_samples_collect_order_id_seq RESTART WITH 7000000000;'
        ),
    ]