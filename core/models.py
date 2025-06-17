from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField
import datetime

class User(Document):
    username = StringField(required=True, unique=True)
    email = EmailField(required=True, unique=True)
    phone = StringField(required=True, unique=True)
    location = StringField()
    password = StringField(required=True)
    is_verified = BooleanField(default=False)
    is_admin = BooleanField(default=False)  # <--- THIS FIELD!
    registered_on = DateTimeField(default=datetime.datetime.utcnow)

class OTP(Document):
    email = EmailField(required=True)
    otp_code = StringField(required=True)
    created_at = DateTimeField(default=datetime.datetime.utcnow)


