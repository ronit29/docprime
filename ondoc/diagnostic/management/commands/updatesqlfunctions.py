from django.core.management.base import BaseCommand
from django.db import migrations

from django.db import connection


class Command(BaseCommand):
    help = 'Create or replace database functions'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:

            cursor.execute(
                '''create or replace function labtest_agreed_price_calculate(mrp numeric, percent numeric)
                    RETURNS numeric LANGUAGE plpgsql STABLE as $$
                    DECLARE
                    agreed_price numeric;
                    BEGIN 
                    agreed_price = ceil(mrp*percent/100);
                    if agreed_price>mrp then 
                    agreed_price=mrp;
                    end if;
                    return agreed_price;
                    END;
                    $$;'''
            )

            cursor.execute(
                '''create or replace function labtest_deal_price_calculate(mrp numeric, agreed_price numeric, percent numeric)
                    RETURNS numeric LANGUAGE plpgsql STABLE as $$
                    DECLARE
                    deal_price numeric;
                    BEGIN 
                    deal_price = ceil(ceil(mrp*percent/100)/10)*10- 1;
                    if deal_price>mrp then 
                    deal_price=mrp;
                    end if;
                    if deal_price<agreed_price then 
                    deal_price=agreed_price;
                    end if;
                    return deal_price;
                    END;
                    $$;'''
            )


