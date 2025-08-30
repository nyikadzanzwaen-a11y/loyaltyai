# LoyaltyAI Platform

A multi-tenant loyalty platform that enables businesses to create and manage customer loyalty programs with AI-powered features.

## Features

- **Multi-tenant Architecture**: Support for multiple businesses with isolated data
- **Loyalty Programs**: Customizable points system and tiered memberships
- **AI-Powered Offers**: Intelligent offer generation and personalization
- **Customer Wallets**: Track points and redemptions
- **Analytics Dashboard**: Business insights and performance metrics

## Tech Stack

- **Backend**: Django 4.2+
- **Frontend**: HTML, CSS, JavaScript, Tailwind CSS
- **Database**: PostgreSQL
- **Task Queue**: Celery
- **AI/ML**: Integrated AI services for offer generation
- **Deployment**: Render.com

## Prerequisites

- Python 3.10+
- PostgreSQL 13+
- Redis (for Celery)
- Git

## Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/nyikadzanzwaen-a11y/loyaltyai.git
   cd loyaltyai
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the project root with the following variables:
   ```
   DEBUG=True
   SECRET_KEY=your-secret-key
   DATABASE_URL=postgresql://user:password@localhost:5432/loyaltyai
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the development server**
   ```bash
   python manage.py runserver
   ```

8. **Start Celery worker** (in a new terminal)
   ```bash
   celery -A loyalty_platform worker --loglevel=info
   ```

## Deployment

This application is configured for deployment on Render.com. To deploy:

1. Push your code to a GitHub repository
2. Connect the repository to Render
3. Set up the environment variables in the Render dashboard
4. Deploy!

## Environment Variables

Required environment variables:

- `DEBUG`: Set to `False` in production
- `SECRET_KEY`: Django secret key
- `DATABASE_URL`: PostgreSQL connection URL
- `REDIS_URL`: Redis connection URL (for Celery)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts

## Project Structure

```
loyalty_platform/
├── accounts/          # User authentication and profiles
├── ai_service/        # AI-powered features
├── api/               # REST API endpoints
├── loyalty/           # Core loyalty program logic
├── tenants/           # Multi-tenancy implementation
├── templates/         # HTML templates
├── static/            # Static files (CSS, JS, images)
└── loyalty_platform/  # Project configuration
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

For any questions or feedback, please contact the project maintainers.
