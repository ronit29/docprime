from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
import jwt
import datetime
from django.conf import settings
from rest_framework import authentication, exceptions
from ondoc.authentication.models import UserSecretKey

User = get_user_model()

class AuthBackend(ModelBackend):
    def authenticate(self, username=None, password=None):
        if '@' in username:
            kwargs = {'email': username, 'user_type': 1}
        else:
            kwargs = {'phone_number': username, 'user_type': 1}
        try:
            user = User.objects.get(**kwargs)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None


    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class JWTAuthentication(authentication.BaseAuthentication):
    authentication_header_prefix = settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX']
    def authenticate(self, request):

        request.user = None

        auth_header = authentication.get_authorization_header(request).split()
        auth_header_prefix = self.authentication_header_prefix.lower()

        if not auth_header:
            return None

        if (len(auth_header) == 1) or (len(auth_header) > 2):
            raise exceptions.AuthenticationFailed('UnAuthorized')

        prefix = auth_header[0].decode('utf-8')
        token = auth_header[1].decode('utf-8')

        if prefix.lower() != auth_header_prefix:
            raise exceptions.AuthenticationFailed('UnAuthorized')

        return self._authenticate_credentials(request, token)


    def _authenticate_credentials(self, request, token):
        user_key = None
        user_id = JWTAuthentication.get_unverified_user(token)
        if user_id:
            user_key_object = UserSecretKey.objects.get(user_id=user_id)
            if user_key_object:
                user_key = user_key_object.key
        try:
            payload = jwt.decode(token, user_key)
        except Exception as e:
            msg = 'Invalid authentication.'
            raise exceptions.AuthenticationFailed(msg)

        try:
            user = User.objects.get(pk=payload['user_id'])
        except User.DoesNotExist:
            msg = 'No user matching this token was found.'
            raise exceptions.AuthenticationFailed(msg)

        if not user.is_active:
            msg = 'This user has been deactivated.'
            raise exceptions.AuthenticationFailed(msg)
        return (user, token)

    def authenticate_header(self, request):
        return self.authentication_header_prefix

    @classmethod
    def jwt_payload_handler(cls, user):
        import calendar
        return {
            'user_id': user.pk,
            'exp': datetime.datetime.utcnow() + settings.JWT_AUTH['JWT_EXPIRATION_DELTA'],
            'orig_iat': calendar.timegm(
                datetime.datetime.utcnow().utctimetuple()
            )
        }

    @staticmethod
    def get_unverified_user(token):
        try:
            unverified_payload = jwt.decode(token, verify=False)
        except Exception as e:
            msg = 'Invalid authentication.'
            raise exceptions.AuthenticationFailed(msg)

        return unverified_payload.get('user_id', None)

