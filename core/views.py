import random
import traceback  # Added for exception handling
from django.core.mail import send_mail
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import OTP, User
from django.contrib.auth.hashers import check_password, make_password
from mongoengine.errors import NotUniqueError
from datetime import datetime, timedelta
import jwt
from datetime import datetime, timedelta
from django.conf import settings


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
        data = request.data
        # Expecting 'email' in request to identify user
        user_email = data.get('email')
        if not user_email:
            return Response({'error': 'User email is required.'}, status=400)
        
        user = User.objects(email=user_email).first()
        if not user:
            return Response({'error': 'User not found.'}, status=404)
        if not user.is_admin:
            return Response({'error': 'Permission denied. Only admin can create schedules.'}, status=403)

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