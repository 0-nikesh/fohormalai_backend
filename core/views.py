import random
import traceback  # Added for exception handling
from django.core.mail import send_mail
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import OTP, CollectionRequest, MarketplacePost, PickupSchedule, User, Notification
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
            coverage_radius_km = float(data.get('coverage_radius_km', 2.0))
        except Exception as e:
            return Response({'error': f'Invalid data: {str(e)}'}, status=400)

        # Create the pickup schedule
        schedule = PickupSchedule(
            admin=user,
            date_time=date_time,
            location=data['location'],
            latitude=latitude,
            longitude=longitude,
            coverage_radius_km=coverage_radius_km,
            garbage_type=data['garbage_type'],
            description=data.get('description', ''),
            status='scheduled'
        )
        schedule.save()

        # Find users within the radius and notify them
        notified_users = self.notify_users_in_radius(schedule)
        
        # Update the schedule with notified users
        schedule.notified_users = notified_users
        schedule.save()

        return Response({
            'message': 'Pickup schedule created successfully.',
            'schedule_id': str(schedule.id),
            'users_notified': len(notified_users)
        }, status=201)
    
    def notify_users_in_radius(self, schedule):
        """Find users within radius and send them notifications"""
        notified_users = []
        
        # Get all verified users with location data
        users = User.objects(is_verified=True, latitude__ne=None, longitude__ne=None)
        
        for user in users:
            # Skip admin users
            if user.is_admin:
                continue
                
            # Calculate distance
            distance = haversine(
                schedule.latitude, schedule.longitude,
                user.latitude, user.longitude
            )
            
            # If user is within radius, notify them
            if distance <= schedule.coverage_radius_km:
                # Create notification
                notification = Notification(
                    user=user,
                    pickup_schedule=schedule,
                    title=f"Pickup Scheduled in Your Area",
                    message=f"A waste pickup for {schedule.garbage_type} is scheduled on {schedule.date_time.strftime('%Y-%m-%d at %H:%M')} near {schedule.location}. Distance: {distance:.2f}km",
                    notification_type="pickup_schedule"
                )
                notification.save()
                
                # Send email notification
                try:
                    send_mail(
                        'Waste Pickup Scheduled in Your Area - FohorMalai',
                        f"""
Dear {user.full_name},

A waste pickup has been scheduled in your area:

📅 Date & Time: {schedule.date_time.strftime('%Y-%m-%d at %H:%M')}
📍 Location: {schedule.location}
🗂️ Waste Type: {schedule.garbage_type}
📏 Distance from you: {distance:.2f}km

{schedule.description if schedule.description else ''}

Please prepare your {schedule.garbage_type} waste for collection.

Best regards,
FohorMalai Team
                        """,
                        'fohormalaideu@gmail.com',
                        [user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print(f"Failed to send email to {user.email}: {str(e)}")
                
                notified_users.append(user)
        
        return notified_users
    

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
            # Fetch user details
            user = User.objects(id=post.user.id).first()
            if user:
                user_details = {
                    'id': str(user.id),
                    'full_name': user.full_name,
                    'email': user.email,
                    'phone': user.phone,
                }
            else:
                user_details = None

            # Include user details in the post response
            result.append({
                'id': str(post.id),
                'user': user_details,
                'title': post.title,
                'description': post.description,
                'hashtags': post.hashtags,
                'price': post.price,
                'quantity': post.quantity,
                'waste_type': post.waste_type,
                'location': post.location,
                'latitude': post.latitude,
                'longitude': post.longitude,
                'image_url': post.image_url,
                'created_at': post.created_at.isoformat(),
            })
        return Response({"posts": result})
    
class CollectionRequestCreateView(APIView):
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

        data = request.data
        required_fields = ['waste_type', 'quantity', 'pickup_date', 'location', 'latitude', 'longitude']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return Response({'error': f'Missing fields: {", ".join(missing)}'}, status=400)

        # Handle image upload
        image_url = ""
        if 'image' in request.FILES:
            try:
                image_url = upload_to_cloudinary(request.FILES['image'])
            except Exception as e:
                return Response({'error': f'Image upload failed: {str(e)}'}, status=400)
        elif data.get('image_url'):
            image_url = data.get('image_url')

        try:
            pickup_date = datetime.fromisoformat(data['pickup_date'])
        except Exception:
            return Response({'error': 'Invalid pickup_date format. Use ISO format.'}, status=400)

        collection_request = CollectionRequest(
            user=user,
            waste_type=data['waste_type'],
            quantity=data['quantity'],
            pickup_date=pickup_date,
            location=data['location'],
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            image_url=image_url,
            special_notes=data.get('special_notes', '')
        )
        collection_request.save()
        return Response({'message': 'Collection request created successfully.'}, status=201)
    
class CollectionRequestListView(APIView):
    def get(self, request):
        # Authenticate user via JWT (optional if you want to personalize results)
        auth_header = request.headers.get('Authorization')
        user = None
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                user_email = payload.get('email')
                user = User.objects(email=user_email).first()
            except Exception:
                pass  # Not strictly required for public listing

        # Get filter parameters if any
        waste_type = request.query_params.get('waste_type')
        status = request.query_params.get('status')
        
        # Location-based filtering
        lat = request.query_params.get('latitude')
        lng = request.query_params.get('longitude')
        radius_km = request.query_params.get('radius_km')
        
        # Base query
        query = {}
        
        # Add filters if provided
        if waste_type:
            query['waste_type'] = waste_type
        if status:
            query['status'] = status
            
        # Get all requests that match query
        requests = CollectionRequest.objects(**query).order_by('-created_at')
        result = []
        
        # Apply radius filter if provided
        if lat and lng and radius_km:
            try:
                lat = float(lat)
                lng = float(lng)
                radius = float(radius_km)
                
                # Filter requests by distance
                for req in requests:
                    dist = haversine(lat, lng, req.latitude, req.longitude)
                    if dist <= radius:
                        # Add to result with distance
                        result.append({
                            "id": str(req.id),
                            "user": str(req.user.full_name) if req.user else "",
                            "waste_type": req.waste_type,
                            "quantity": req.quantity,
                            "pickup_date": req.pickup_date.isoformat(),
                            "location": req.location,
                            "latitude": req.latitude,
                            "longitude": req.longitude,
                            "image_url": req.image_url,
                            "special_notes": req.special_notes,
                            "status": req.status,
                            "distance_km": round(dist, 2),
                            "created_at": req.created_at.isoformat()
                        })
            except (ValueError, TypeError):
                # If parameters are invalid, return all results without distance filtering
                pass
        else:
            # No location filtering, return all results
            for req in requests:
                result.append({
                    "id": str(req.id),
                    "user": str(req.user.full_name) if req.user else "",
                    "waste_type": req.waste_type,
                    "quantity": req.quantity,
                    "pickup_date": req.pickup_date.isoformat(),
                    "location": req.location,
                    "latitude": req.latitude,
                    "longitude": req.longitude,
                    "image_url": req.image_url,
                    "special_notes": req.special_notes,
                    "status": req.status,
                    "created_at": req.created_at.isoformat()
                })
                
        return Response({"collection_requests": result})
    

class CollectionRequestStatusUpdateView(APIView):
    def patch(self, request, request_id):
        # Authenticate user via JWT and verify admin status
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
            
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_email = payload.get('email')
            is_admin = payload.get('is_admin', False)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
            
        # Only admin can update status
        if not is_admin:
            return Response({'error': 'Permission denied. Only admin can update collection request status.'}, status=403)
            
        # Get the collection request
        try:
            collection_request = CollectionRequest.objects.get(id=request_id)
        except Exception:
            return Response({'error': 'Collection request not found.'}, status=404)
            
        # Validate the new status
        new_status = request.data.get('status')
        valid_statuses = ['pending', 'out_for_collection', 'completed', 'cancelled']
        
        if not new_status or new_status not in valid_statuses:
            return Response({
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }, status=400)
            
        # Update the status
        collection_request.status = new_status
        collection_request.save()
        
        return Response({
            'message': 'Collection request status updated successfully.',
            'request_id': str(collection_request.id),
            'new_status': new_status
        })
    
from collections import defaultdict
from math import radians, cos, sin, asin, sqrt

class AdminCollectionHeatmapView(APIView):
    def get(self, request):
        # Authenticate admin
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        # Get all collection requests
        collection_requests = CollectionRequest.objects()
        
        # Get clustering radius parameter (in kilometers)
        radius_km = float(request.query_params.get('radius_km', 1.0))
        
        # Create clusters
        clusters = self.cluster_locations(collection_requests, radius_km)
        
        return Response({
            'clusters': clusters,
            'total_requests': len(collection_requests)
        })
    
    def cluster_locations(self, collection_requests, radius_km):
        """Group collection requests into clusters based on proximity."""
        if not collection_requests:
            return []
        
        # Map of cluster center to list of requests
        clusters = []
        processed = set()
        
        for i, req in enumerate(collection_requests):
            if str(req.id) in processed:
                continue
                
            # Start a new cluster
            cluster = {
                'center': {
                    'latitude': req.latitude,
                    'longitude': req.longitude,
                    'location': req.location
                },
                'count': 1,
                'request_ids': [str(req.id)],
                'statuses': {req.status: 1},
                'waste_types': {req.waste_type: 1}
            }
            processed.add(str(req.id))
            
            # Find all other requests within radius
            for j, other_req in enumerate(collection_requests):
                if i == j or str(other_req.id) in processed:
                    continue
                    
                # Calculate distance
                dist = haversine(req.latitude, req.longitude, 
                                other_req.latitude, other_req.longitude)
                
                if dist <= radius_km:
                    # Add to cluster
                    cluster['count'] += 1
                    cluster['request_ids'].append(str(other_req.id))
                    
                    # Update status counts
                    if other_req.status in cluster['statuses']:
                        cluster['statuses'][other_req.status] += 1
                    else:
                        cluster['statuses'][other_req.status] = 1
                        
                    # Update waste type counts
                    if other_req.waste_type in cluster['waste_types']:
                        cluster['waste_types'][other_req.waste_type] += 1
                    else:
                        cluster['waste_types'][other_req.waste_type] = 1
                        
                    processed.add(str(other_req.id))
            
            clusters.append(cluster)
        
        # Sort clusters by count (largest first)
        return sorted(clusters, key=lambda x: x['count'], reverse=True)
    
class BulkCollectionRequestUpdateView(APIView):
    def put(self, request):
        # Authenticate admin
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        # Get request data
        data = request.data
        required_fields = ['latitude', 'longitude', 'radius_km', 'pickup_date', 'status']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return Response({'error': f'Missing fields: {", ".join(missing)}'}, status=400)

        try:
            latitude = float(data['latitude'])
            longitude = float(data['longitude'])
            radius_km = float(data['radius_km'])
            pickup_date = datetime.fromisoformat(data['pickup_date'])
        except (ValueError, TypeError):
            return Response({'error': 'Invalid latitude, longitude, radius_km, or pickup_date format'}, status=400)

        # Find all collection requests within the radius
        collection_requests = CollectionRequest.objects(status='pending')
        requests_in_radius = []
        
        for req in collection_requests:
            distance = haversine(latitude, longitude, req.latitude, req.longitude)
            if distance <= radius_km:
                requests_in_radius.append(req)

        if not requests_in_radius:
            return Response({'error': 'No collection requests found in the specified radius'}, status=404)

        # Create a pickup schedule for this cluster
        admin = User.objects(email=payload.get('email')).first()
        schedule = PickupSchedule(
            admin=admin,
            date_time=pickup_date,
            location=requests_in_radius[0].location,  # Use location of first request
            latitude=latitude,
            longitude=longitude,
            coverage_radius_km=radius_km,
            garbage_type="Mixed",  # Or determine based on requests
            description=f"Bulk pickup for {len(requests_in_radius)} requests",
            status='scheduled'
        )
        schedule.save()

        # Update all requests in radius and notify users
        updated_count = 0
        notified_users = set()
        
        for req in requests_in_radius:
            try:
                req.status = data['status']
                req.pickup_schedule = schedule
                req.save()
                updated_count += 1

                # Create notification for the user
                if req.user not in notified_users:
                    notification = Notification(
                        user=req.user,
                        pickup_schedule=schedule,
                        title="Collection Request Scheduled",
                        message=f"""Your collection request has been scheduled for pickup on 
                                  {pickup_date.strftime('%Y-%m-%d at %H:%M')}.""",
                        notification_type="collection_schedule"
                    )
                    notification.save()

                    # Send email notification
                    try:
                        send_mail(
                            'Collection Request Scheduled - FohorMalai',
                            f"""
Dear {req.user.full_name},

Your collection request has been scheduled for pickup:

📅 Date & Time: {pickup_date.strftime('%Y-%m-%d at %H:%M')}
📍 Location: {req.location}
🗑️ Status: {data['status']}

Please ensure your waste is properly segregated and ready for collection.

Best regards,
FohorMalai Team
                            """,
                            'fohormalaideu@gmail.com',
                            [req.user.email],
                            fail_silently=True,
                        )
                    except Exception as e:
                        print(f"Failed to send email to {req.user.email}: {str(e)}")

                    notified_users.add(req.user)

            except Exception as e:
                print(f"Error updating request {req.id}: {str(e)}")
                continue

        return Response({
            'message': f'Updated {updated_count} collection requests',
            'schedule_id': str(schedule.id),
            'total_requests': len(requests_in_radius),
            'updated_requests': updated_count,
            'users_notified': len(notified_users),
            'pickup_date': pickup_date.isoformat(),
            'coverage_area': {
                'latitude': latitude,
                'longitude': longitude,
                'radius_km': radius_km
            }
        })
class PickupScheduleListView(APIView):
    def get(self, request):
        """Get all pickup schedules (admin only)"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        # Get filter parameters
        status = request.query_params.get('status')
        garbage_type = request.query_params.get('garbage_type')
        
        # Build query
        query = {}
        if status:
            query['status'] = status
        if garbage_type:
            query['garbage_type'] = garbage_type
        
        schedules = PickupSchedule.objects(**query).order_by('-created_at')
        result = []
        
        for schedule in schedules:
            result.append({
                'id': str(schedule.id),
                'admin': schedule.admin.full_name if schedule.admin else 'Unknown',
                'date_time': schedule.date_time.isoformat(),
                'location': schedule.location,
                'latitude': schedule.latitude,
                'longitude': schedule.longitude,
                'coverage_radius_km': schedule.coverage_radius_km,
                'garbage_type': schedule.garbage_type,
                'description': schedule.description,
                'status': schedule.status,
                'users_notified': len(schedule.notified_users) if schedule.notified_users else 0,
                'created_at': schedule.created_at.isoformat()
            })
        
        return Response({'pickup_schedules': result})

class PickupScheduleUpdateView(APIView):
    def patch(self, request, schedule_id):
        """Update pickup schedule status"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        try:
            schedule = PickupSchedule.objects.get(id=schedule_id)
        except:
            return Response({'error': 'Pickup schedule not found.'}, status=404)
        
        new_status = request.data.get('status')
        valid_statuses = ['scheduled', 'in_progress', 'completed', 'cancelled']
        
        if not new_status or new_status not in valid_statuses:
            return Response({
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }, status=400)
        
        schedule.status = new_status
        schedule.save()
        
        return Response({
            'message': 'Pickup schedule status updated successfully.',
            'schedule_id': str(schedule.id),
            'new_status': new_status
        })

class UserNotificationsView(APIView):
    def get(self, request):
        """Get notifications for logged-in user"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_email = payload.get('email')
            user = User.objects(email=user_email).first()
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        if not user:
            return Response({'error': 'User not found.'}, status=404)
        
        # Get query parameters
        is_read = request.query_params.get('is_read')
        
        query = {'user': user}
        if is_read is not None:
            query['is_read'] = is_read.lower() == 'true'
        
        notifications = Notification.objects(**query).order_by('-sent_at')
        result = []
        
        for notification in notifications:
            result.append({
                'id': str(notification.id),
                'title': notification.title,
                'message': notification.message,
                'notification_type': notification.notification_type,
                'is_read': notification.is_read,
                'sent_at': notification.sent_at.isoformat(),
                'pickup_schedule': {
                    'id': str(notification.pickup_schedule.id),
                    'date_time': notification.pickup_schedule.date_time.isoformat(),
                    'location': notification.pickup_schedule.location
                } if notification.pickup_schedule else None
            })
        
        return Response({'notifications': result})
    
    def patch(self, request):
        """Mark notifications as read"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_email = payload.get('email')
            user = User.objects(email=user_email).first()
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        if not user:
            return Response({'error': 'User not found.'}, status=404)
        
        notification_ids = request.data.get('notification_ids', [])
        
        if not notification_ids:
            # Mark all as read
            Notification.objects(user=user, is_read=False).update(is_read=True)
            return Response({'message': 'All notifications marked as read.'})
        else:
            # Mark specific notifications as read
            count = 0
            for notification_id in notification_ids:
                try:
                    notification = Notification.objects.get(id=notification_id, user=user)
                    notification.is_read = True
                    notification.save()
                    count += 1
                except:
                    continue
            
            return Response({'message': f'{count} notifications marked as read.'})

class AdminDashboardStatsView(APIView):
    def get(self, request):
        """Get dashboard statistics for admin"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        # Get statistics
        total_users = User.objects(is_verified=True, is_admin=False).count()
        total_collection_requests = CollectionRequest.objects().count()
        pending_requests = CollectionRequest.objects(status='pending').count()
        completed_requests = CollectionRequest.objects(status='completed').count()
        total_schedules = PickupSchedule.objects().count()
        active_schedules = PickupSchedule.objects(status__in=['scheduled', 'in_progress']).count()
        total_marketplace_posts = MarketplacePost.objects().count()
        
        # Recent activity
        recent_requests = CollectionRequest.objects().order_by('-created_at').limit(5)
        recent_schedules = PickupSchedule.objects().order_by('-created_at').limit(5)
        
        stats = {
            'overview': {
                'total_users': total_users,
                'total_collection_requests': total_collection_requests,
                'pending_requests': pending_requests,
                'completed_requests': completed_requests,
                'total_schedules': total_schedules,
                'active_schedules': active_schedules,
                'total_marketplace_posts': total_marketplace_posts
            },
            'recent_requests': [
                {
                    'id': str(req.id),
                    'user': req.user.full_name,
                    'waste_type': req.waste_type,
                    'status': req.status,
                    'created_at': req.created_at.isoformat()
                } for req in recent_requests
            ],
            'recent_schedules': [
                {
                    'id': str(schedule.id),
                    'location': schedule.location,
                    'garbage_type': schedule.garbage_type,
                    'date_time': schedule.date_time.isoformat(),
                    'status': schedule.status
                } for schedule in recent_schedules
            ]
        }
        
        return Response(stats)

class AdminUsersListView(APIView):
    def get(self, request):
        """Get all users for admin management"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        # Get filter parameters
        search = request.query_params.get('search', '')
        status = request.query_params.get('status', '')
        role = request.query_params.get('role', '')
        location = request.query_params.get('location', '')
        
        # Build query
        query = {}
        if search:
            # Search in name or email
            query['$or'] = [
                {'full_name__icontains': search},
                {'email__icontains': search}
            ]
        if status == 'verified':
            query['is_verified'] = True
        elif status == 'unverified':
            query['is_verified'] = False
            
        if role == 'admin':
            query['is_admin'] = True
        elif role == 'user':
            query['is_admin'] = False
            
        if location:
            query['location__icontains'] = location
        
        users = User.objects(**query).order_by('-registered_on')
        result = []
        
        for user in users:
            result.append({
                'id': str(user.id),
                'full_name': user.full_name,
                'email': user.email,
                'phone': user.phone,
                'location': user.location,
                'latitude': user.latitude,
                'longitude': user.longitude,
                'is_verified': user.is_verified,
                'is_admin': user.is_admin,
                'registered_on': user.registered_on.isoformat()
            })
        
        return Response({
            'users': result,
            'total_count': len(result)
        })

class AdminDashboardView(APIView):
    def get(self, request):
        """Get complete dashboard data"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        # Get statistics
        total_users = User.objects(is_verified=True, is_admin=False).count()
        total_collection_requests = CollectionRequest.objects().count()
        pending_collections = CollectionRequest.objects(status='pending').count()
        completed_collections = CollectionRequest.objects(status='completed').count()
        marketplace_posts = MarketplacePost.objects().count()
        
        # Calculate changes (mock data for now - you can implement actual comparison)
        pending_change = 5.2  # You can calculate this based on previous period
        completed_change = 12.8
        marketplace_change = 8.1
        users_change = 15.3
        
        # Get recent activities
        recent_requests = CollectionRequest.objects().order_by('-created_at').limit(5)
        recent_marketplace = MarketplacePost.objects().order_by('-created_at').limit(3)
        recent_schedules = PickupSchedule.objects().order_by('-created_at').limit(3)
        
        recent_activities = []
        
        # Add collection requests to activities
        for req in recent_requests:
            recent_activities.append({
                'id': str(req.id),
                'type': 'collection',
                'message': f'New collection request for {req.waste_type} by {req.user.full_name}',
                'timestamp': req.created_at.isoformat(),
                'user': req.user.full_name,
                'metadata': {
                    'waste_type': req.waste_type,
                    'status': req.status,
                    'location': req.location
                }
            })
        
        # Add marketplace posts to activities
        for post in recent_marketplace:
            recent_activities.append({
                'id': str(post.id),
                'type': 'marketplace',
                'message': f'New marketplace post: {post.title} by {post.user.full_name}',
                'timestamp': post.created_at.isoformat(),
                'user': post.user.full_name,
                'metadata': {
                    'title': post.title,
                    'price': post.price,
                    'waste_type': post.waste_type
                }
            })
        
        # Add pickup schedules to activities
        for schedule in recent_schedules:
            recent_activities.append({
                'id': str(schedule.id),
                'type': 'system',
                'message': f'Pickup scheduled for {schedule.garbage_type} at {schedule.location}',
                'timestamp': schedule.created_at.isoformat(),
                'user': schedule.admin.full_name if schedule.admin else 'System',
                'metadata': {
                    'garbage_type': schedule.garbage_type,
                    'location': schedule.location,
                    'status': schedule.status
                }
            })
        
        # Sort activities by timestamp
        recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_activities = recent_activities[:10]  # Limit to 10 most recent
        
        # Get waste collection trends (mock data - you can implement actual trends)
        from datetime import datetime, timedelta
        import calendar
        
        trends = []
        current_date = datetime.now()
        for i in range(30):  # Last 30 days
            date = current_date - timedelta(days=i)
            # You can calculate actual counts here
            count = CollectionRequest.objects(
                created_at__gte=date.replace(hour=0, minute=0, second=0),
                created_at__lt=date.replace(hour=23, minute=59, second=59)
            ).count()
            
            trends.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count,
                'waste_type': 'Mixed'  # You can break this down by actual waste types
            })
        
        dashboard_data = {
            'stats': {
                'total_collection_requests': total_collection_requests,
                'pending_collections': pending_collections,
                'completed_collections': completed_collections,
                'marketplace_posts': marketplace_posts,
                'active_users': total_users,
                'total_waste_collected': completed_collections * 5,  # Assuming 5kg average
                'pending_change': pending_change,
                'completed_change': completed_change,
                'marketplace_change': marketplace_change,
                'users_change': users_change
            },
            'recent_activities': recent_activities,
            'waste_collection_trends': trends
        }
        
        return Response(dashboard_data)

class AdminDashboardActivitiesView(APIView):
    def get(self, request):
        """Get recent activities for dashboard"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        limit = int(request.query_params.get('limit', 10))
        
        # Get recent activities from various sources
        recent_requests = CollectionRequest.objects().order_by('-created_at').limit(limit//2)
        recent_marketplace = MarketplacePost.objects().order_by('-created_at').limit(limit//2)
        
        activities = []
        
        for req in recent_requests:
            activities.append({
                'id': str(req.id),
                'type': 'collection',
                'message': f'New collection request for {req.waste_type}',
                'timestamp': req.created_at.isoformat(),
                'user': req.user.full_name,
                'metadata': {
                    'waste_type': req.waste_type,
                    'status': req.status
                }
            })
        
        for post in recent_marketplace:
            activities.append({
                'id': str(post.id),
                'type': 'marketplace',
                'message': f'New marketplace post: {post.title}',
                'timestamp': post.created_at.isoformat(),
                'user': post.user.full_name,
                'metadata': {
                    'title': post.title,
                    'price': post.price
                }
            })
        
        # Sort by timestamp
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return Response({'activities': activities[:limit]})

class AdminAnalyticsView(APIView):
    def get(self, request):
        """Get analytics data for admin"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        # Get query parameters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        waste_type = request.query_params.get('waste_type')
        location = request.query_params.get('location')
        
        # Build query filters
        query = {}
        if start_date:
            try:
                start = datetime.fromisoformat(start_date)
                query['created_at__gte'] = start
            except:
                pass
        
        if end_date:
            try:
                end = datetime.fromisoformat(end_date)
                query['created_at__lte'] = end
            except:
                pass
        
        if waste_type and waste_type != 'All Types':
            query['waste_type'] = waste_type
        
        if location:
            query['location__icontains'] = location
        
        # Get analytics data
        collection_requests = CollectionRequest.objects(**query)
        marketplace_posts = MarketplacePost.objects(**query)
        
        # Aggregate data by waste type
        waste_type_stats = {}
        for req in collection_requests:
            if req.waste_type not in waste_type_stats:
                waste_type_stats[req.waste_type] = {'count': 0, 'completed': 0}
            waste_type_stats[req.waste_type]['count'] += 1
            if req.status == 'completed':
                waste_type_stats[req.waste_type]['completed'] += 1
        
        # Location-wise statistics
        location_stats = {}
        for req in collection_requests:
            loc = req.location.split(',')[0]  # Get first part of location
            if loc not in location_stats:
                location_stats[loc] = 0
            location_stats[loc] += 1
        
        analytics_data = {
            'total_requests': collection_requests.count(),
            'total_marketplace_posts': marketplace_posts.count(),
            'waste_type_breakdown': waste_type_stats,
            'location_breakdown': location_stats,
            'completion_rate': (
                collection_requests.filter(status='completed').count() / 
                max(collection_requests.count(), 1) * 100
            ),
            'period': {
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
        return Response(analytics_data)

class AdminPickupSchedulesUsersInRadiusView(APIView):
    def get(self, request):
        """Get users within a specified radius for pickup scheduling"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        # Get query parameters
        try:
            latitude = float(request.query_params.get('latitude'))
            longitude = float(request.query_params.get('longitude'))
            radius_km = float(request.query_params.get('radius_km', 2.0))
        except (TypeError, ValueError):
            return Response({'error': 'Invalid latitude, longitude, or radius_km parameters.'}, status=400)
        
        # Get all verified users with location data
        users = User.objects(is_verified=True, latitude__ne=None, longitude__ne=None, is_admin=False)
        
        users_in_radius = []
        for user in users:
            # Calculate distance using haversine formula
            distance = haversine(latitude, longitude, user.latitude, user.longitude)
            
            if distance <= radius_km:
                users_in_radius.append({
                    'id': str(user.id),
                    'full_name': user.full_name,
                    'email': user.email,
                    'phone': user.phone,
                    'location': user.location,
                    'latitude': user.latitude,
                    'longitude': user.longitude,
                    'distance_km': round(distance, 2),
                    'registered_on': user.registered_on.isoformat()
                })
        
        # Sort by distance
        users_in_radius.sort(key=lambda x: x['distance_km'])
        
        return Response({
            'users': users_in_radius,
            'total_count': len(users_in_radius),
            'search_parameters': {
                'latitude': latitude,
                'longitude': longitude,
                'radius_km': radius_km
            }
        })

class AdminPickupSchedulesListView(APIView):
    def get(self, request):
        """Get all pickup schedules for admin management"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
        
        # Get filter parameters
        status = request.query_params.get('status')
        garbage_type = request.query_params.get('garbage_type')
        location = request.query_params.get('location')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Build query
        query = {}
        if status:
            query['status'] = status
        if garbage_type:
            query['garbage_type'] = garbage_type
        if location:
            query['location__icontains'] = location
        if start_date:
            try:
                start = datetime.fromisoformat(start_date)
                query['date_time__gte'] = start
            except:
                pass
        if end_date:
            try:
                end = datetime.fromisoformat(end_date)
                query['date_time__lte'] = end
            except:
                pass
        
        schedules = PickupSchedule.objects(**query).order_by('-created_at')
        result = []
        
        for schedule in schedules:
            result.append({
                'id': str(schedule.id),
                'admin': {
                    'id': str(schedule.admin.id),
                    'name': schedule.admin.full_name,
                    'email': schedule.admin.email
                } if schedule.admin else None,
                'date_time': schedule.date_time.isoformat(),
                'location': schedule.location,
                'latitude': schedule.latitude,
                'longitude': schedule.longitude,
                'coverage_radius_km': schedule.coverage_radius_km,
                'garbage_type': schedule.garbage_type,
                'description': schedule.description,
                'status': schedule.status,
                'notified_users_count': len(schedule.notified_users) if schedule.notified_users else 0,
                'notified_users': [
                    {
                        'id': str(user.id),
                        'name': user.full_name,
                        'email': user.email,
                        'location': user.location
                    } for user in schedule.notified_users
                ] if schedule.notified_users else [],
                'created_at': schedule.created_at.isoformat()
            })
        
        return Response({
            'pickup_schedules': result,
            'total_count': len(result),
            'filters_applied': {
                'status': status,
                'garbage_type': garbage_type,
                'location': location,
                'start_date': start_date,
                'end_date': end_date
            }
        })
    
    def post(self, request):
        """Create a new pickup schedule (alternative endpoint)"""
        # This is essentially the same as PickupScheduleCreateView
        # But provides a more RESTful endpoint structure
        
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
            coverage_radius_km = float(data.get('coverage_radius_km', 2.0))
        except Exception as e:
            return Response({'error': f'Invalid data: {str(e)}'}, status=400)

        # Create the pickup schedule
        schedule = PickupSchedule(
            admin=user,
            date_time=date_time,
            location=data['location'],
            latitude=latitude,
            longitude=longitude,
            coverage_radius_km=coverage_radius_km,
            garbage_type=data['garbage_type'],
            description=data.get('description', ''),
            status='scheduled'
        )
        schedule.save()

        # Find users within the radius and notify them
        notified_users = self.notify_users_in_radius(schedule)
        
        # Update the schedule with notified users
        schedule.notified_users = notified_users
        schedule.save()

        return Response({
            'message': 'Pickup schedule created successfully.',
            'schedule': {
                'id': str(schedule.id),
                'date_time': schedule.date_time.isoformat(),
                'location': schedule.location,
                'garbage_type': schedule.garbage_type,
                'coverage_radius_km': schedule.coverage_radius_km,
                'users_notified': len(notified_users)
            }
        }, status=201)
    
    def notify_users_in_radius(self, schedule):
        """Find users within radius and send them notifications"""
        notified_users = []
        
        # Get all verified users with location data
        users = User.objects(is_verified=True, latitude__ne=None, longitude__ne=None)
        
        for user in users:
            # Skip admin users
            if user.is_admin:
                continue
                
            # Calculate distance
            distance = haversine(
                schedule.latitude, schedule.longitude,
                user.latitude, user.longitude
            )
            
            # If user is within radius, notify them
            if distance <= schedule.coverage_radius_km:
                # Create notification
                notification = Notification(
                    user=user,
                    pickup_schedule=schedule,
                    title=f"Pickup Scheduled in Your Area",
                    message=f"A waste pickup for {schedule.garbage_type} is scheduled on {schedule.date_time.strftime('%Y-%m-%d at %H:%M')} near {schedule.location}. Distance: {distance:.2f}km",
                    notification_type="pickup_schedule"
                )
                notification.save()
                
                # Send email notification
                try:
                    send_mail(
                        'Waste Pickup Scheduled in Your Area - FohorMalai',
                        f"""
Dear {user.full_name},

A waste pickup has been scheduled in your area:

📅 Date & Time: {schedule.date_time.strftime('%Y-%m-%d at %H:%M')}
📍 Location: {schedule.location}
🗂️ Waste Type: {schedule.garbage_type}
📏 Distance from you: {distance:.2f}km

{schedule.description if schedule.description else ''}

Please prepare your {schedule.garbage_type} waste for collection.

Best regards,
FohorMalai Team
                        """,
                        'fohormalaideu@gmail.com',
                        [user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print(f"Failed to send email to {user.email}: {str(e)}")
                
                notified_users.append(user)
        
        return notified_users

class UserCollectionRequestsView(APIView):
    def get(self, request, user_email=None):
        """Get collection requests for a specific user"""
        # Authenticate user via JWT
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            current_user_email = payload.get('email')
            is_admin = payload.get('is_admin', False)
            current_user = User.objects(email=current_user_email).first()
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
            
        if not current_user:
            return Response({'error': 'User not found.'}, status=404)
            
        # If user_email is provided, check permissions
        if user_email:
            # Only admin or the user themselves can view their specific requests
            if not is_admin and current_user_email != user_email:
                return Response({'error': 'You do not have permission to view this user\'s requests.'}, status=403)
                
            target_user = User.objects(email=user_email).first()
            if not target_user:
                return Response({'error': 'User not found.'}, status=404)
            query = {'user': target_user}
        else:
            # If no user_email provided, use the current authenticated user
            query = {'user': current_user}
            
        # Get filter parameters
        status = request.query_params.get('status')
        waste_type = request.query_params.get('waste_type')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        
        # Apply filters
        if status:
            query['status'] = status
        if waste_type:
            query['waste_type'] = waste_type
        if from_date:
            try:
                from_datetime = datetime.fromisoformat(from_date)
                query['created_at__gte'] = from_datetime
            except ValueError:
                pass
        if to_date:
            try:
                to_datetime = datetime.fromisoformat(to_date)
                query['created_at__lte'] = to_datetime
            except ValueError:
                pass
        
        # Get the collection requests
        collection_requests = CollectionRequest.objects(**query).order_by('-created_at')
        
        # Format the response
        result = []
        for req in collection_requests:
            result.append({
                "id": str(req.id),
                "user": {
                    "id": str(req.user.id),
                    "full_name": req.user.full_name,
                    "email": req.user.email,
                    "phone": req.user.phone  # Added phone number
                },
                "waste_type": req.waste_type,
                "quantity": req.quantity,
                "pickup_date": req.pickup_date.isoformat(),
                "location": req.location,
                "latitude": req.latitude,
                "longitude": req.longitude,
                "image_url": req.image_url,
                "special_notes": req.special_notes,
                "status": req.status,
                "created_at": req.created_at.isoformat()
            })
            
        return Response({
            "collection_requests": result,
            "total": len(result),
            "user_email": user_email or current_user_email,
            "filters": {
                "status": status,
                "waste_type": waste_type,
                "from_date": from_date,
                "to_date": to_date
            }
        })
class UserPickupSchedulesView(APIView):
    def get(self, request):
        """Get pickup schedules that have notified the current user"""
        # Authenticate user via JWT
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_email = payload.get('email')
            current_user = User.objects(email=user_email).first()
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)
            
        if not current_user:
            return Response({'error': 'User not found.'}, status=404)
            
        # Get filter parameters
        status = request.query_params.get('status')
        garbage_type = request.query_params.get('garbage_type')
        upcoming_only = request.query_params.get('upcoming_only', 'false').lower() == 'true'
        
        # Find schedules where this user is in notified_users
        query = {'notified_users': current_user}
        
        # Apply filters
        if status:
            query['status'] = status
        if garbage_type:
            query['garbage_type'] = garbage_type
        if upcoming_only:
            query['date_time__gte'] = datetime.utcnow()
        
        # Get the pickup schedules
        schedules = PickupSchedule.objects(**query).order_by('date_time')
        
        # Format the response
        result = []
        for schedule in schedules:
            # Calculate distance from user to pickup location
            distance = haversine(
                current_user.latitude, current_user.longitude,
                schedule.latitude, schedule.longitude
            ) if current_user.latitude and current_user.longitude else None
            
            result.append({
                "id": str(schedule.id),
                "admin": {
                    "id": str(schedule.admin.id),
                    "name": schedule.admin.full_name,
                } if schedule.admin else None,
                "date_time": schedule.date_time.isoformat(),
                "location": schedule.location,
                "latitude": schedule.latitude,
                "longitude": schedule.longitude,
                "garbage_type": schedule.garbage_type,
                "description": schedule.description,
                "status": schedule.status,
                "distance_km": round(distance, 2) if distance else None,
                "created_at": schedule.created_at.isoformat(),
                "is_upcoming": schedule.date_time > datetime.utcnow()
            })
            
        return Response({
            "pickup_schedules": result,
            "total": len(result),
            "filters": {
                "status": status,
                "garbage_type": garbage_type,
                "upcoming_only": upcoming_only
            }
        })

class UserProfileView(APIView):
    def get(self, request):
        """Fetch the authenticated user's personal details"""
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

        print(f"Authorization header: {auth_header}")
        print(f"Decoded payload: {payload}")
        print(f"User email: {user_email}")
        print(f"User object: {user}")

        return Response({
            'id': str(user.id),
            'name': user.full_name,
            'email': user.email,
            'location': user.location,
            'latitude': user.latitude,
            'longitude': user.longitude,
            'is_verified': user.is_verified,
            'is_admin': user.is_admin,
            'phone': user.phone,
        })
    

# class ActivePickupsView(APIView):
#   def get(self, request):
#         """Get active pickups for the current date"""
#         auth_header = request.headers.get('Authorization')
#         print(f"Authorization header: {auth_header}")
        
#         # Validate and clean Authorization header
#         if not auth_header or not auth_header.startswith('Bearer '):
#             return Response({'error': 'Authorization header missing or invalid.'}, status=401)
        
#         # Remove duplicate 'Bearer ' if present
#         token = auth_header.replace('Bearer ', '', 1).strip()
#         try:
#             payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
#             print(f"Decoded payload: {payload}")
#             user_email = payload.get('email')
#             current_user = User.objects(email=user_email).first()
#         except jwt.ExpiredSignatureError:
#             print("Token has expired.")
#             return Response({'error': 'Token has expired.'}, status=401)
#         except jwt.InvalidTokenError:
#             print("Invalid token.")
#             return Response({'error': 'Invalid token.'}, status=401)
#         except Exception as e:
#             print(f"Error decoding token: {str(e)}")
#             return Response({'error': 'Invalid or expired token.'}, status=401)
            
#         if not current_user:
#             return Response({'error': 'User not found.'}, status=404)
        
        
#         # Get today's date
#         today = datetime.utcnow().date()
        
#         # Query active pickups (scheduled or in progress) for today
#         active_pickups = PickupSchedule.objects(
#             status__in=['scheduled', 'in_progress'],
#             date_time__gte=datetime(today.year, today.month, today.day),
#             date_time__lt=datetime(today.year, today.month, today.day) + timedelta(days=1)
#         ).order_by('date_time')
        
#         # Format the response
#         result = []
#         for pickup in active_pickups:
#             result.append({
#                 "id": str(pickup.id),
#                 "location": pickup.location,
#                 "latitude": pickup.latitude,
#                 "longitude": pickup.longitude,
#                 "date_time": pickup.date_time.isoformat(),
#                 "status": pickup.status,
#                 "garbage_type": pickup.garbage_type,
#                 "description": pickup.description,
#             })
        
#         return Response({
#             "active_pickups": result,
#             "total": len(result),
#             "date": today.isoformat()
#         })

class ActivePickupsView(APIView):
    def get(self, request):
        """Get active pickups for the current date"""
        auth_header = request.headers.get('Authorization')
        print(f"Authorization header: {auth_header}")

        # Validate and clean Authorization header
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)

        # Remove duplicate 'Bearer ' if present
        token = auth_header.replace('Bearer ', '', 1).strip()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            print(f"Decoded payload: {payload}")
            user_email = payload.get('email')
            current_user = User.objects(email=user_email).first()
        except jwt.ExpiredSignatureError:
            print("Token has expired.")
            return Response({'error': 'Token has expired.'}, status=401)
        except jwt.InvalidTokenError:
            print("Invalid token.")
            return Response({'error': 'Invalid token.'}, status=401)
        except Exception as e:
            print(f"Error decoding token: {str(e)}")
            return Response({'error': 'Invalid or expired token.'}, status=401)

        if not current_user:
            return Response({'error': 'User not found.'}, status=404)

        # Get today's date
        today = datetime.utcnow().date()

        # Query active pickups (scheduled or in progress) for today
        try:
            active_pickups = PickupSchedule.objects(
                status__in=['scheduled', 'in_progress'],
                date_time__gte=datetime(today.year, today.month, today.day),
                date_time__lt=datetime(today.year, today.month, today.day) + timedelta(days=1)
            ).order_by('date_time')
        except Exception as e:
            print(f"Error querying active pickups: {str(e)}")
            return Response({'error': 'Failed to query active pickups.'}, status=500)

        # Format the response
        result = []
        for pickup in active_pickups:
            result.append({
                "id": str(pickup.id),
                "location": pickup.location,
                "latitude": pickup.latitude,
                "longitude": pickup.longitude,
                "date_time": pickup.date_time.isoformat(),
                "status": pickup.status,
                "garbage_type": pickup.garbage_type,
                "description": pickup.description,
            })

        return Response({
            "active_pickups": result,
            "total": len(result),
            "date": today.isoformat()
        })
class AdminAnalyticsPerformanceView(APIView):
    def get(self, request):
        """Get performance metrics for analytics"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)

        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)

        # Mock data for performance metrics
        metrics = {
            'average_completion_time': 24.5,
            'pickup_efficiency': 85.3,
            'user_satisfaction': 92.7,
            'total_waste_diverted': 1250.0
        }

        return Response({'metrics': metrics})


class AdminAnalyticsWasteTrendsView(APIView):
    def get(self, request):
        """Get waste collection trends"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)

        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)

        # Mock data for waste trends
        trends = [
            {'date': '2025-07-01', 'total_requests': 50, 'completed_requests': 40, 'waste_types': {'Plastic': 20, 'Organic': 15, 'Metal': 5}},
            {'date': '2025-07-02', 'total_requests': 60, 'completed_requests': 50, 'waste_types': {'Plastic': 25, 'Organic': 20, 'Metal': 15}},
        ]

        return Response({'trends': trends})


class AdminAnalyticsWasteDistributionView(APIView):
    def get(self, request):
        """Get waste type distribution"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)

        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)

        # Mock data for waste distribution
        distribution = [
            {'waste_type': 'Plastic', 'count': 100, 'percentage': 40.0},
            {'waste_type': 'Organic', 'count': 80, 'percentage': 32.0},
            {'waste_type': 'Metal', 'count': 70, 'percentage': 28.0},
        ]

        return Response({'distribution': distribution})


class AdminAnalyticsLocationStatsView(APIView):
    def get(self, request):
        """Get location-based analytics"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)

               
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)

        # Mock data for location stats
        locations = [
            {'location': 'New York', 'request_count': 50, 'completion_rate': 80.0, 'popular_waste_types': ['Plastic', 'Organic']},
            {'location': 'Los Angeles', 'request_count': 40, 'completion_rate': 75.0, 'popular_waste_types': ['Metal', 'Plastic']},
        ]

        return Response({'locations': locations})


class AdminAnalyticsUserEngagementView(APIView):
    def get(self, request):
        """Get user engagement analytics"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)

        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            is_admin = payload.get('is_admin', False)
            if not is_admin:
                return Response({'error': 'Admin access required.'}, status=403)
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)

        # Mock data for user engagement
        engagement = [
            {'date': '2025-07-01', 'new_users': 10, 'active_users': 50, 'collection_requests': 30, 'marketplace_posts': 20},
            {'date': '2025-07-02', 'new_users': 15, 'active_users': 60, 'collection_requests': 40, 'marketplace_posts': 25},
        ]

        return Response({'engagement': engagement})

class UserDetailsView(APIView):
    def get(self, request, user_id):
        """Fetch user details by user ID"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'error': 'Authorization header missing or invalid.'}, status=401)

        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            current_user_email = payload.get('email')
            current_user = User.objects(email=current_user_email).first()
        except Exception:
            return Response({'error': 'Invalid or expired token.'}, status=401)

        if not current_user:
            return Response({'error': 'User not found.'}, status=404)

        # Fetch user details by ID
        target_user = User.objects(id=user_id).first()
        if not target_user:
            return Response({'error': 'User not found.'}, status=404)

        return Response({
            'id': str(target_user.id),
            'name': target_user.full_name,
            'email': target_user.email,
            'phone': target_user.phone,
            'location': target_user.location,
            'latitude': target_user.latitude,
            'longitude': target_user.longitude,
        })
