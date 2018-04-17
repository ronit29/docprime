import datetime
from ondoc.doctor.models import Doctor
from collections import OrderedDict, defaultdict


class RestructureDataService():
    """.Restructures timings and availability given by serializer."""

    def reform_timings(self, days):
        sorted_results_by_days = defaultdict(list)
        result = []

        # sorting results by hospital id
        for avl in days:
            sorted_results_by_days[avl['day']].append(avl)

        for key,val in sorted_results_by_days.items():
            temp = {"day": key, 'time': []}
            for v in val:
                temp['time'].append({
                    'from': v['start'],
                    'to': v['end'],
                    'fee': v['fees']
                })
            result.append(temp)

        return result


    def reform_availability(self, availability):
        sorted_results_by_hospitals = defaultdict(list)
        result = []

        today = datetime.datetime.today().weekday() + 1
        curr_hour = datetime.datetime.now().hour

        # sorting results by hospital id
        for avl in availability:
            sorted_results_by_hospitals[avl['hospital_id']].append(avl)

        for key,val in sorted_results_by_hospitals.items():
            temp = {"hospital_id": key, 'days': [], 'nextAvailable': []}
            for v in val:
                temp['name'] = v['hospital']
                temp['address'] = v['address']
                temp['days'].append({'day': v['day'], 'start': v['start'], 
                    'end': v['end'], 'fees': v['fees']})

                if v['day'] == today and v['start'] > curr_hour:
                    temp['nextAvailable'].append({
                        'day': 0,
                        'from': v['start'],
                        'to': v['end'],
                        'fee': {
                            'amount': v['fees'],
                            'discounted': 0, 
                        }
                    })
                else:
                    temp['nextAvailable'].append({
                        'day': (v['day'] - today) if v['day'] - today >= 0 else (v['day'] - today + 7),
                        'from': v['start'],
                        'to': v['end'],
                        'fee': {
                            'amount': v['fees'],
                            'discounted': 0, 
                        }
                    })
                sorted(temp['nextAvailable'], key = lambda x: (x['day'], x['from']))
            result.append(temp)

        return result


class ReformScheduleService():
    """Restructure the data given by serializer, and get n days schedule"""

    def __init__(self, schedule = [], days = 10):
        self.schedule = schedule
        self.days = days

    def generate_schedule(self, schedule_by_day = {}):
        day = datetime.datetime.today().weekday()
        date = datetime.date.today()
        curr_hour = datetime.datetime.now().hour
        schedule_dates = []

        # Now that we have schedule by days, we will generate next n dates schedule of doctor
        for _ in range(self.days):
            if day >= 7:
                day = day%7

            temp = {
                "date": date,
                "intervals": schedule_by_day[day]
            }

            schedule_dates.append(temp)

            #update date and day
            date = date + datetime.timedelta(days=1)
            day = day + 1

        return schedule_dates

    def get_data(self, *args, **kwargs):
        # divide current schedule by day in dictionay
        schedule_by_day = defaultdict(list)

        for sch in self.schedule:
            schedule_by_day[sch['day'] -1].append(sch)

        schedule_dates = self.generate_schedule(schedule_by_day = schedule_by_day)

        restruct_obj = RestructureDataService()
        for single_date in schedule_dates:
            single_date['intervals'] = restruct_obj.reform_timings(single_date['intervals'])

        return schedule_dates

