# Fohormalai Backend

## Overview
Fohormalai Backend is a Django-based API server designed to manage waste collection, pickup schedules, marketplace posts, and analytics for waste management operations. It provides endpoints for both admin and user functionalities, including authentication, notifications, and analytics.

## Features
### User Features
- **Authentication**: Register, login, and OTP-based verification.
- **Notifications**: View notifications related to waste pickups and other activities.
- **Pickup Schedules**: View upcoming waste pickup schedules.
- **Collection Requests**: Create and manage waste collection requests.

### Admin Features
- **Dashboard**: View statistics and recent activities.
- **Analytics**: Access detailed analytics for waste management operations.
- **Pickup Schedules**: Manage pickup schedules and notify users within a radius.
- **Marketplace**: Manage marketplace posts for waste-related items.

### Analytics
- **Performance Metrics**: Average completion time, pickup efficiency, user satisfaction, and total waste diverted.
- **Waste Trends**: Daily trends for waste collection requests and completions.
- **Waste Distribution**: Breakdown of waste types and their percentages.
- **Location Stats**: Analytics based on user locations.
- **User Engagement**: Insights into new users, active users, and their activities.

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/0-nikesh/fohormalai_backend.git
   ```
2. Navigate to the project directory:
   ```bash
   cd fohormalai_backend
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the server:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

## API Endpoints
### User Endpoints
- `POST /api/register/`: Register a new user.
- `POST /api/login/`: Login and receive a JWT token.
- `GET /api/user/me/`: Fetch authenticated user details.
- `GET /api/user/notifications/`: View user notifications.
- `GET /api/user/pickup-schedules/`: View pickup schedules.

### Admin Endpoints
- `GET /api/admin/dashboard/`: View admin dashboard.
- `GET /api/admin/analytics/performance/`: View performance metrics.
- `GET /api/admin/analytics/waste-trends/`: View waste trends.
- `GET /api/admin/analytics/waste-distribution/`: View waste distribution.
- `GET /api/admin/analytics/location-stats/`: View location-based analytics.
- `GET /api/admin/analytics/user-engagement/`: View user engagement analytics.

### Collection Requests
- `POST /api/collection-request/`: Create a new collection request.
- `GET /api/get-collection-request/`: View collection requests.
- `PATCH /api/collection-request/<request_id>/status/`: Update collection request status.

### Marketplace
- `POST /api/marketplace-post/`: Create a new marketplace post.
- `GET /api/get-marketplace-post/`: View marketplace posts.

## Technologies Used
- **Django**: Backend framework.
- **Django REST Framework**: API development.
- **MongoEngine**: MongoDB integration.
- **JWT Authentication**: Secure user authentication.

## Contributing
1. Fork the repository.
2. Create a new branch:
   ```bash
   git checkout -b feature-branch
   ```
3. Make your changes and commit them:
   ```bash
   git commit -m "Add new feature"
   ```
4. Push to your branch:
   ```bash
   git push origin feature-branch
   ```
5. Create a pull request.

## License
This project is licensed under the MIT License.

## Contact
For any inquiries, please contact [0-nikesh](mailto:0nikesh0@gmail.com).
