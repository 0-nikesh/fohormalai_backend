from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, FloatField, ReferenceField, ListField, ImageField
import datetime

class User(Document):
    full_name = StringField(required=True)  
    email = EmailField(required=True, unique=True)
    phone = StringField(required=True, unique=True)
    location = StringField()
    latitude = FloatField()
    longitude = FloatField()
    password = StringField(required=True)
    is_verified = BooleanField(default=False)
    is_admin = BooleanField(default=False)  
    registered_on = DateTimeField(default=datetime.datetime.utcnow)

class OTP(Document):
    email = EmailField(required=True)
    otp_code = StringField(required=True)
    created_at = DateTimeField(default=datetime.datetime.utcnow)

class PickupSchedule(Document):
    date_time = DateTimeField(required=True)
    location = StringField(required=True)
    latitude = FloatField(required=True)
    longitude = FloatField(required=True)
    garbage_type = StringField(required=True)  # e.g., 'organic', 'plastic', etc.

    meta = {'collection': 'pickup_schedules'}

class MarketplacePost(Document):
    user = ReferenceField('User', required=True)  # Reference to the posting user
    title = StringField(required=True)            # Short title or product name
    description = StringField(required=True)      # Detailed description
    hashtags = ListField(StringField())           # List of hashtags (e.g., ['#Sell', '#organic'])
    price = FloatField(required=True)             # Price in Nrs or your currency
    quantity = StringField()                      # e.g., '10Kg'
    waste_type = StringField(required=True)       # e.g., 'compost manure', 'paper', etc.
    location = StringField(required=True)         # Human-readable location
    latitude = FloatField(required=True)
    longitude = FloatField(required=True)
    image_url = StringField()                     # Store image URL or path
    created_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {'collection': 'marketplace_posts'}

