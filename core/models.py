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
    admin = ReferenceField('User', required=True)  # Admin who created the schedule
    date_time = DateTimeField(required=True)
    location = StringField(required=True)
    latitude = FloatField(required=True)
    longitude = FloatField(required=True)
    coverage_radius_km = FloatField(required=True, default=2.0)  # Radius in kilometers
    garbage_type = StringField(required=True)  # e.g., 'organic', 'plastic', etc.
    description = StringField()  # Additional details about the pickup
    status = StringField(default="scheduled")  # scheduled, in_progress, completed, cancelled
    notified_users = ListField(ReferenceField('User'))  # Users who were notified
    created_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {'collection': 'pickup_schedules'}

class MarketplacePost(Document):
    user = ReferenceField('User', required=True)  # Reference to the posting user
    title = StringField(required=True)            # Short title or product name
    description = StringField(required=True)      # Detailed description
    hashtags = ListField(StringField())           # List of hashtags (e.g., ['#Sell', '#organic'])
    price = FloatField(required=True)             # Price in Nrs or your currency
    quantity = StringField()                      # e.g., '10Kg'
    waste_type = StringField(required=True)       
    location = StringField(required=True)     
    latitude = FloatField(required=True)
    longitude = FloatField(required=True)
    image_url = StringField()                  
    created_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {'collection': 'marketplace_posts'}

class CollectionRequest(Document):
    user = ReferenceField('User', required=True)
    waste_type = StringField(required=True)
    quantity = StringField(required=True)
    pickup_date = DateTimeField(required=True)
    location = StringField(required=True)
    latitude = FloatField(required=True)
    longitude = FloatField(required=True)
    image_url = StringField()
    special_notes = StringField()
    status = StringField(default="pending")  # Add this line with a default value
    created_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {'collection': 'collection_requests'}

class Notification(Document):
    user = ReferenceField('User', required=True)
    pickup_schedule = ReferenceField('PickupSchedule', required=True)
    title = StringField(required=True)
    message = StringField(required=True)
    notification_type = StringField(default="pickup_schedule")  # pickup_schedule, status_update, etc.
    is_read = BooleanField(default=False)
    sent_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {'collection': 'notifications'}

