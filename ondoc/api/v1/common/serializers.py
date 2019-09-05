from fluent_comments.models import FluentComment
from rest_framework import serializers

from ondoc.common.models import GlobalNonBookable, DeviceDetails, LastUsageTimestamp, DocumentsProofs
from ondoc.authentication.models import UserProfile, User
from ondoc.common.models import GlobalNonBookable, AppointmentHistory
from ondoc.diagnostic.models import Lab
from ondoc.lead.models import SearchLead


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailServiceSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=1000)
    to = serializers.ListField(child=serializers.EmailField(), min_length=1, max_length=10)
    cc = serializers.ListField(child=serializers.EmailField(), required=False, max_length=10)


class SMSServiceSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500)
    phone_number = serializers.IntegerField()


class XlsSerializer(serializers.Serializer):
    file = serializers.FileField()


class DoctorXLSerializer(serializers.Serializer):
    file = serializers.FileField()
    source = serializers.CharField(max_length=20)
    batch = serializers.CharField(max_length=20)


class SearchLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchLead
        fields = '__all__'


class GlobalNonBookableSerializer(serializers.ModelSerializer):
    interval = serializers.CharField(read_only=True)
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    start_time = serializers.FloatField(read_only=True, source='start_time_in_float')
    end_time = serializers.FloatField(read_only=True, source='end_time_in_float')

    class Meta:
        model = GlobalNonBookable
        exclude = ('booking_type', 'created_at', 'updated_at', 'deleted_at')


class DeviceDetailsSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    data = serializers.JSONField(required=False)

    class Meta:
        model = DeviceDetails
        exclude = ('created_at', 'updated_at', 'id', 'user')


class LastUsageTimestampSerializer(serializers.ModelSerializer):

    class Meta:
        model = LastUsageTimestamp
        exclude = ('created_at', 'updated_at', 'id', 'last_app_open_timestamp', 'phone_number', 'device')


class AppointmentPrerequisiteSerializer(serializers.Serializer):
    lab_test = serializers.ListField(child=serializers.IntegerField(), required=True)
    lab = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.all(), required=True)
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), required=True)
    # start_date = serializers.DateTimeField(required=True)


class CommentSerializer(serializers.ModelSerializer):
    #children = RecursiveField(many=True)
    children = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    profile_img = serializers.SerializerMethodField()

    def get_profile_img(self, obj):
        profile_image = None

        user = obj.user
        if user and user.user_type == User.CONSUMER:
            profile = user.profiles.filter(is_default_user=True).first()
            if profile:
                profile_image = profile.get_thumbnail()

        #if not profile image

        return profile_image

    def get_children(self, obj):
        if len(obj.children.filter(is_public=True))>0:
            return CommentSerializer(obj.children.filter(is_public=True), many=True).data
        return None

    def get_author(self, obj):
        author_details = dict()
        author_details['name'] = obj.user_name if obj and obj.user_name else 'Anonymous'
        author_details['experience'] = None
        author_details['profile_img'] = None
        author_details['speciality'] = None
        author_details['rating'] = None
        author_details['url'] = None
        return author_details

    class Meta:
        model = FluentComment
        fields = (
            'id',
            'comment',
            'children',
            'submit_date',
            'user_name',
            'author',
            'profile_img',
           )


class DocumentProofUploadSerializer(serializers.ModelSerializer):
    # prescription_file = serializers.FileField(max_length=None, use_url=True)
    class Meta:
        model = DocumentsProofs
        fields = ('proof_file', 'user')
