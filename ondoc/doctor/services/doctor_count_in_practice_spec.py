from ondoc.api.v1.utils import RawSql


class DoctorSearchScore:
    def update_doctors_count(self):
        RawSql('''update practice_specialization ps set doctor_count=
                coalesce((select doctor_count from 
                (select ps.id specialization_id, count(distinct d.id) as doctor_count from doctor d inner join 
                 doctor_practice_specialization dps on d.id = dps.doctor_id
                inner join practice_specialization ps on ps.id = dps.specialization_id
                group by ps.id)x where x.specialization_id = ps.id),0)
                ''', []).execute()
        return "success"