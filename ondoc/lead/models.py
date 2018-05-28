from django.db import models
from django.contrib.postgres.fields import JSONField
from django.contrib.gis.geos import Point
from ondoc.doctor.models import Hospital,  Doctor, DoctorHospital


class HospitalLead(models.Model):
    source_id = models.PositiveIntegerField()
    city = models.CharField(max_length=100)
    lab = models.CharField(max_length=256)
    hospital = models.OneToOneField(Hospital, on_delete=models.SET_NULL, null=True, blank=True)
    json = JSONField()

    def __str__(self):
        return "{}-{}".format(self.lab, self.id)

    class Meta:
        db_table = "hospital_lead"


class DoctorLead(models.Model):
    source_id = models.PositiveIntegerField()
    city = models.CharField(max_length=100)
    lab = models.CharField(max_length=256)
    doctor = models.OneToOneField(Doctor, on_delete=models.SET_NULL, null=True, blank=True)
    json = JSONField()
    hospital_leads = models.ManyToManyField(
        HospitalLead,
        through='DoctorHospitalLead',
        through_fields=('doctor_lead', 'hospital_lead'),
    )

    def __str__(self):
        return "{}-{}".format(self.lab, self.id)

    class Meta:
        db_table = "doctor_lead"

    def convert_lead(self, user):
        doctor = self.create_doctor(user)
        self.doctor = doctor
        for hospital in self.json.get("LinkedClinics").values():
            clinic_url = hospital[2].get("Clinic URL")
            visiting_days = hospital[0].get("Visiting Days")
            fees = hospital[1].get("Fee").split()[-1]
            hospital_lead = HospitalLead.objects.filter(json__URL=clinic_url).first()
            if not hospital_lead:
                continue
            hospital = self.create_hospital(hospital_lead, user)
            hospital_lead.hospital = hospital
            self.create_doctor_hospital(doctor, hospital, visiting_days, fees)
            hospital_lead.save()
        self.save()

    def create_doctor(self, user):
        name = self.json.get("Name")
        created_by = user
        gender = ""
        doctor = Doctor.objects.create(name=name,
                                       created_by=created_by,
                                       gender=gender)
        if not doctor:
            return
        return doctor

    def create_hospital(self, hospital_lead, created_by):
        if not hospital_lead:
            return
        HOSPITAL_TYPE_MAPPING = {hospital_type[1]: hospital_type[0]
                                 for hospital_type in Hospital.HOSPITAL_TYPE_CHOICES}
        hospital_name = hospital_lead.json.get("Name")
        hospital_type = hospital_lead.json.get("ClinicOrHospital")
        hospital_type = HOSPITAL_TYPE_MAPPING.get(hospital_type)
        location = (hospital_lead.json.get("GoogleAddress")
                    .split("/")[-1].split(",") if self.json.get("GoogleAddress").split("/") else None)
        location_point = Point(float(location[1]), float(location[0]), srid=4326) if len(location) == 2 else None
        hospital = Hospital.objects.create(
            name=hospital_name,
            hospital_type=hospital_type,
            location=location_point,
            created_by=created_by
        )
        return hospital

    def create_doctor_hospital(self, doctor, hospital, visiting_days, fees):
        DAYS_MAPPING = {
            "Mon": 0,
            "Tue": 1,
            "Wed": 2,
            "Thu": 3,
            "Fri": 4,
            "Sat": 5,
            "Sun": 6,
        }
        TIME_SLOT_MAPPING = {time_slot_choice[1]: time_slot_choice[0] for time_slot_choice in
                             DoctorHospital.TIME_SLOT_CHOICES}
        for key, value in visiting_days.items():
            for day_range_str in key.split(","):
                day_range = range(DAYS_MAPPING.get(day_range_str.strip().split("-")[0].strip()),
                                  DAYS_MAPPING.get(day_range_str.strip().split("-")[-1].strip()) + 1)
                for day in day_range:
                    for timing in value:
                        start_time = timing.split("-")[0].strip()
                        end_time = timing.split("-")[-1].strip()
                        start_time_db_value = (
                            TIME_SLOT_MAPPING.get("{} {}".format(start_time.split(":")[0], start_time.split(" ")[-1]))
                        )
                        end_time_db_value = (
                            TIME_SLOT_MAPPING.get("{} {}".format(end_time.split(":")[0], end_time.split(" ")[-1]))
                        )
                        if (not start_time_db_value) or (not end_time_db_value):
                            continue
                        DoctorHospital.objects.create(
                            doctor=doctor,
                            hospital=hospital,
                            day=day,
                            start=start_time_db_value,
                            end=end_time_db_value,
                            fees=fees
                        )


class DoctorHospitalLead(models.Model):
    doctor_lead = models.ForeignKey(DoctorLead, on_delete=models.SET_NULL, null=True, blank=True)
    hospital_lead = models.ForeignKey(HospitalLead, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "doctor_hospital_lead"

    def __str__(self):
        return "doctor-lead-{} hospital-lead-{}".format(self.doctor_lead.id,
                                                        self.hospital_lead.id)