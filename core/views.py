import random
from django.core.mail import send_mail
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import OTP

class SendOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')
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
    

from .models import User, OTP
from django.contrib.auth.hashers import make_password

class RegisterView(APIView):
    def post(self, request):
        data = request.data
        otp_entry = OTP.objects(email=data['email']).order_by('-created_at').first()

        if not otp_entry or otp_entry.otp_code != data['otp']:
            return Response({'error': 'Invalid or expired OTP'}, status=400)

        user = User(
            username=data['username'],
            email=data['email'],
            phone=data['phone'],
            location=data['location'],
            password=make_password(data['password']),
            is_verified=True
        )
        user.save()
        return Response({'message': 'User registered successfully'})


from django.contrib.auth.hashers import check_password

class LoginView(APIView):
    def post(self, request):
        data = request.data
        try:
            user = User.objects.get(email=data['email'])
            if check_password(data['password'], user.password):
                return Response({
                                'message': 'Login successful',
                                'is_admin': user.is_admin
                                })
            else:
                return Response({'error': 'Incorrect password'}, status=401)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)

