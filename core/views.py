import random
import traceback  # Added for exception handling
from django.core.mail import send_mail
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import OTP, MarketplacePost, PickupSchedule, User
from django.contrib.auth.hashers import check_password, make_password
from mongoengine.errors import NotUniqueError
from datetime import datetime, timedelta
import jwt
from datetime import datetime, timedelta
from django.conf import settings
from math import radians, cos, sin, asin, sqrt
import cloudinary.uploader



class SendOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required.'}, status=400)
        otp = str(random.randint(100000, 999999))
        OTP(email=email, otp_code=otp).save()

        send_mail(
            'Your FohorMalai OTP Code',
            f'Your OTP is {otp}',
            'your_email@gmail.com',
            [email],
            fail_silently=False,
        )

        return Response({'message': 'OTP sent successfully'})

class RegisterView(APIView):
    def post(self, request):
        data = request.data
        required_fields = ['full_name', 'email', 'phone', 'otp', 'location', 'password', 'latitude', 'longitude']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return Response({'error': f'Missing required fields: {", ".join(missing)}'}, status=400)

        email = data.get('email')
        phone = data.get('phone')
        full_name = data.get('full_name')
        otp_code = data.get('otp')
        location = data.get('location')
        password = data.get('password')

        try:
            latitude = float(data.get('latitude'))
            longitude = float(data.get('longitude'))
        except (TypeError, ValueError):
            return Response({'error': 'Latitude and longitude must be valid numbers.'}, status=400)

        if User.objects(email=email).first():
            return Response({'error': 'An account with this email already exists.'}, status=409)
        if User.objects(phone=phone).first():
            return Response({'error': 'An account with this phone number already exists.'}, status=409)

        otp_entry = OTP.objects(email=email).order_by('-created_at').first()
        if not otp_entry or otp_entry.otp_code != otp_code:
            return Response({'error': 'Invalid or expired OTP.'}, status=400)

        if datetime.utcnow() > otp_entry.created_at + timedelta(minutes=5):
            return Response({'error': 'OTP has expired. Please request a new one.'}, status=400)

        try:
            user = User(
                full_name=full_name,
                email=email,
                phone=phone,
                location=location,
                latitude=latitude,
                longitude=longitude,
                password=make_password(password),
                is_verified=True
            )
            user.save()
            otp_entry.delete()
            return Response({'message': 'User registered successfully'}, status=201)

        except NotUniqueError:
            return Response({'error': 'User already exists (duplicate key).'}, status=409)

        except Exception as e:
            print(traceback.format_exc())
            return Response({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

class LoginView(APIView):
    def post(self, request):
        data = request.data
        if not data.get('email') or not data.get('password'):
            return Response({'error': 'Email and password are required.'}, status=400)
        try:
            user = User.objects.get(email=data['email'])
            if check_password(data['password'], user.password):
                payload = {
                    'email': user.email,
                    'is_admin': user.is_admin,
                    'exp': datetime.utcnow() + timedelta(hours=24)
                }
                token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
                return Response({
                    'message': 'Login successful',
                    'is_admin': user.is_admin,
                    'token': token
                })
            else:
                return Response({'error': 'Incorrect password'}, status=401)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404) 
 
class PickupScheduleCreateView(APIView):
    def post(self, request):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        token = auth_header.split(' ')[1]

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_email = payload.get('email')
        except Exception as e:
            return Response({'error': 'Invalid or expired token.'}, status=401)

        user = User.objects(email=user_email).first()
        if not user:
            return Response({'error': 'User not found.'}, status=404)
        if not user.is_admin:
            return Response({'error': 'Permission denied. Only admin can create schedules.'}, status=403)

        data = request.data
        required_fields = ['date_time', 'location', 'latitude', 'longitude', 'garbage_type']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return Response({'error': f'Missing fields: {", ".join(missing)}'}, status=400)

        try:
            date_time = datetime.fromisoformat(data['date_time'])
            latitude = float(data['latitude'])
            longitude = float(data['longitude'])
        except Exception as e:
            return Response({'error': f'Invalid data: {str(e)}'}, status=400)

        schedule = PickupSchedule(
            date_time=date_time,
            location=data['location'],
            latitude=latitude,
            longitude=longitude,
            garbage_type=data['garbage_type']
        )
        schedule.save()
        return Response({'message': 'Pickup schedule created successfully.'}, status=201)
    

def haversine(lat1, lon1, lat2, lon2):
    # Calculate the great circle distance between two points on the earth (in km)
    R = 6371  # Earth radius in kilometers
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

class NearbyPickupSchedulesView(APIView):
    def get(self, request):
        # Get user from token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_email = payload.get('email')
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)

        user = User.objects(email=user_email).first()
        if not user:
            return Response({'error': 'User not found.'}, status=404)
        if not user.latitude or not user.longitude:
            return Response({'error': 'User location not set.'}, status=400)

        user_lat = user.latitude
        user_lon = user.longitude

        schedules = PickupSchedule.objects()
        nearby = []
        for sched in schedules:
            dist = haversine(user_lat, user_lon, sched.latitude, sched.longitude)
            if dist <= 2:  # 2km radius
                nearby.append({
                    "date_time": sched.date_time,
                    "location": sched.location,
                    "latitude": sched.latitude,
                    "longitude": sched.longitude,
                    "garbage_type": sched.garbage_type,
                    "distance_km": round(dist, 2)
                })
        return Response({"schedules": nearby})
    
import cloudinary

cloudinary.config(
    cloud_name='davmrc5zy',
    api_key='819849725819125',
    api_secret='gohKLTozQDjlh1zKo30qMVYCk24'
)

def upload_to_cloudinary(file):
    result = cloudinary.uploader.upload(file)
    return result['secure_url']

class MarketplacePostCreateView(APIView):
    def post(self, request):
        # Authenticate user via JWT
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_email = payload.get('email')
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)

        user = User.objects(email=user_email).first()
        if not user:
            return Response({'error': 'User not found.'}, status=404)

        # Required fields
        data = request.data
        required_fields = ['title', 'description', 'price', 'waste_type', 'location', 'latitude', 'longitude']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return Response({'error': f'Missing fields: {", ".join(missing)}'}, status=400)

        # Handle hashtags
        hashtags = data.get('hashtags', [])
        if isinstance(hashtags, str):
            hashtags = [h.strip() for h in hashtags.split(',') if h.strip()]

        # Handle image upload
        image_url = ""
        if 'image' in request.FILES:
            try:
                image_url = upload_to_cloudinary(request.FILES['image'])
            except Exception as e:
                return Response({'error': f'Image upload failed: {str(e)}'}, status=400)
        elif data.get('image_url'):
            image_url = data.get('image_url')

        post = MarketplacePost(
            user=user,
            title=data['title'],
            description=data['description'],
            hashtags=hashtags,
            price=float(data['price']),
            quantity=data.get('quantity', ''),
            waste_type=data['waste_type'],
            location=data['location'],
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            image_url=image_url
        )
        post.save()
        return Response({'message': 'Marketplace post created successfully.'}, status=201)    

class MarketplacePostListView(APIView):
    def get(self, request):
        # Optional: Authenticate user if you want to personalize results
        auth_header = request.headers.get('Authorization')
        user = None
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                user_email = payload.get('email')
                user = User.objects(email=user_email).first()
            except Exception:
                pass  # Not strictly required for public wall

        posts = MarketplacePost.objects().order_by('-created_at')
        result = []
        for post in posts:
            result.append({
                "id": str(post.id),
                "user": str(post.user.full_name) if post.user else "",
                "title": post.title,
                "description": post.description,
                "hashtags": post.hashtags,
                "price": post.price,
                "quantity": post.quantity,
                "waste_type": post.waste_type,
                "location": post.location,
                "latitude": post.latitude,
                "longitude": post.longitude,
                "image_url": post.image_url,
                "created_at": post.created_at.isoformat()
            })
        return Response({"posts": result})
    
