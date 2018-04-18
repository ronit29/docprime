from django.db import models

class Lab(TimeStampedModel, CreatedByModel, QCModel):
    name = models.CharField(max_length=200)
    about = models.CharField(max_length=1000, blank=True)
    license = models.CharField(max_length=200, blank=True)
    operational_since = models.PositiveSmallIntegerField(blank=True, null=True,  validators=[MinValueValidator(1800)])
    parking = models.PositiveSmallIntegerField(blank = True, null = True, choices=[("","Select"), (1,"Easy"), (2,"Difficult")])
    always_open = models.BooleanField(verbose_name= 'Is lab open 24X7', default=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.SET_NULL)
    network_type = models.PositiveSmallIntegerField(blank = True, null = True, choices=[("","Select"), (1,"Non Network Lab"), (2,"Network Lab")])
    network = models.ForeignKey('LabNetwork', null=True, blank=True, on_delete=models.SET_NULL)
    location = models.PointField(geography=True, srid=4326, blank=True, null=True)
    location_error = models.PositiveIntegerField(blank=True, null=True)
    building = models.CharField(max_length=100, blank=True)
    sublocality = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pin_code = models.PositiveIntegerField(blank=True, null=True)


class LabCertification(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.lab.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_certification"


class LabAccreditation(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.lab.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_accreditation"


class LabAward(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])

    def __str__(self):
        return self.lab.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_award"


class LabManager(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    number = models.BigIntegerField()
    email = models.EmailField(max_length=100, blank=True)
    details = models.CharField(max_length=200, blank=True)
    contact_type = models.PositiveSmallIntegerField(choices=[(1, "Other"), (2, "Single Point of Contact"), (3, "Manager"), (4, "Owner")])


class LabImage(TimeStampedModel, Image):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    name = models.ImageField(upload_to='lab/images',height_field='height', width_field='width')

    class Meta:
        db_table = "lab_image"


class LabTiming(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)

    day = models.PositiveSmallIntegerField(blank=False, null=False, choices=[(1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"), (5, "Friday"), (6, "Saturday"), (7, "Sunday")])
    start = models.PositiveSmallIntegerField(
        blank=False, null=False, choices=[(6, "6 AM"), (7, "7 AM"),
        (8, "8 AM"), (9, "9 AM"), (10, "10 AM"), (11, "11 AM"),
        (12, "12 PM"), (13, "1 PM"), (14, "2 PM"), (15, "3 PM"),
        (16, "4 PM"), (17, "5 PM"), (18, "6 PM"), (19, "7 PM"),
        (20, "8 PM"), (21, "9 PM"), (22, "10 PM"), (23, "11 PM")])
    end = models.PositiveSmallIntegerField(
        blank=False, null=False, choices=[(6, "6 AM"), (7, "7 AM"),
        (8, "8 AM"), (9, "9 AM"), (10, "10 AM"), (11, "11 AM"),
        (12, "12 PM"), (13, "1 PM"), (14, "2 PM"), (15, "3 PM"),
        (16, "4 PM"), (17, "5 PM"), (18, "6 PM"), (19, "7 PM"),
        (20, "8 PM"), (21, "9 PM"), (22, "10 PM"), (23, "11 PM")])

    class Meta:
        db_table = "lab_timing"





class LabNetwork(TimeStampedModel, CreatedByModel, QCModel):
    name = models.CharField(max_length=100)
    operational_since = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1900)])
    about = models.CharField(max_length=2000, blank=True)
    network_size = models.PositiveSmallIntegerField(blank=True, null=True)
    building = models.CharField(max_length=100, blank=True)
    sublocality = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pin_code = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return self.name + " (" + self.city + ")"

    class Meta:
        db_table = "lab_network"


class LabNetworkCertification(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_network_certification"


class LabNetworkAward(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])
    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_network_award"


class LabNetworkAccreditation(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_network_accreditation"

class LabNetworkManager(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    number = models.BigIntegerField()
    email = models.EmailField(max_length=100, blank=True)
    details = models.CharField(max_length=200, blank=True)
    contact_type = models.PositiveSmallIntegerField(choices=[(1, "Other"), (2, "Single Point of Contact"), (3, "Manager")])

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "lab_network_manager"


class LabNetworkHelpline(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    number = models.BigIntegerField()
    details = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "lab_network_helpline"


class LabNetworkEmail(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    email = models.EmailField(max_length=100)

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "lab_network_email"


class PathologyTestType(TimeStampedModel):
    name = models.CharField(max_length=200)


class RadiologyTestType(TimeStampedModel):
    name = models.CharField(max_length=200)


class PathologyTest(TimeStampedModel):
    name = models.CharField(max_length=200)
    test_type = models.ForeignKey(PathologyTestType, on_delete=models.SET_NULL)
    test_sub_type = models.ForeignKey(PathologyTestType, on_delete=models.SET_NULL)
    is_package = models.BooleanField(verbose_name= 'Is this test package type?')
    why = models.CharField(max_length=1000, blank=True)
    pre_test_info = models.CharField(max_length=1000, blank=True)
    sample_handling_instructions = models.CharField(max_length=1000, blank=True)
    sample_collection_instructions = models.CharField(max_length=1000, blank=True)
    sample_amount = models.CharField(max_length=1000, blank=True)
    expected_tat = models.CharField(max_length=1000, blank=True)

    class Meta:
        db_table = "pathalogy_test"

class RadiologyTest(TimeStampedModel):
    name = models.CharField(max_length=200)
    test_type = models.ForeignKey(RadiologyTestType, on_delete=models.SET_NULL)
    test_sub_type = models.ForeignKey(RadiologyTestType, on_delete=models.SET_NULL)
    is_package = models.BooleanField(verbose_name= 'Is this test package type?')
    why = models.CharField(max_length=1000, blank=True)
    pre_test_info = models.CharField(max_length=1000, blank=True)
