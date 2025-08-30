import random
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
import uuid

from loyalty.models import Offer, CustomerWallet
from .models import CustomerSegment, ChurnPrediction, AIGeneratedOffer

class AIService:
    """Service class for AI functionality."""
    
    @staticmethod
    def _parse_uuid(value):
        """Return a uuid.UUID if value is a valid UUID, else None."""
        try:
            if isinstance(value, uuid.UUID):
                return value
            s = str(value).strip()
            if not s:
                return None
            return uuid.UUID(s)
        except (ValueError, TypeError, AttributeError):
            return None
    
    @staticmethod
    def generate_personalized_offer(customer_id, business_id, context=None):
        """
        Generate a personalized offer for a customer.
        
        In production, this would call an LLM API, but for the prototype
        we use a mock implementation.
        """
        if not settings.AI_SERVICE_ENABLED:
            return None
        
        # In a real implementation, fetch customer data and call AI API
        if settings.AI_SERVICE_MOCK:
            return AIService._mock_generate_offer(customer_id, business_id, context)
        else:
            # Here would be code to call the real AI service
            pass
    
    @staticmethod
    def _mock_generate_offer(customer_id, business_id, context=None):
        """Mock implementation of offer generation for the prototype."""
        offer_types = ['discount', 'points_multiplier', 'free_item']
        offer_type = random.choice(offer_types)
        
        # Get customer wallet to personalize based on points
        customer_uuid = AIService._parse_uuid(customer_id)
        points_balance = 0
        if customer_uuid:
            try:
                wallet = CustomerWallet.objects.get(customer_id=customer_uuid, business_id=business_id)
                points_balance = wallet.points_balance
            except CustomerWallet.DoesNotExist:
                points_balance = 0
        
        # Context aware modifications
        time_context = context.get('time_of_day', 'day') if context else 'day'
        day_context = context.get('day_of_week', 'weekday') if context else 'weekday'
        
        # Create offer based on mock personalization logic
        if offer_type == 'discount':
            # Higher discount for higher point balances
            base_discount = 10
            bonus = min(points_balance // 1000, 15)  # Cap bonus at 15%
            discount = base_discount + bonus
            
            # Weekend discounts are higher
            if day_context == 'weekend':
                discount += 5
            
            title = f"{discount}% Off Your Next Purchase"
            description = f"As a valued customer, enjoy {discount}% off your next purchase!"
            offer_data = {
                'title': title,
                'description': description,
                'type': 'discount',
                'discount_percentage': discount,
                'points_required': max(100, min(points_balance // 2, 500)),
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=7),
                'is_active': True,
                'is_ai_generated': True
            }
            
        elif offer_type == 'points_multiplier':
            # Points multiplier based on activity time
            multiplier = 2.0
            if time_context == 'morning':
                title = "Morning Boost: 2x Points"
                description = "Start your day right! Earn double points on all purchases before 11 AM."
            elif time_context == 'evening':
                multiplier = 3.0
                title = "Evening Special: 3x Points"
                description = "Reward yourself after a long day! Earn triple points on all purchases after 6 PM."
            else:
                title = "Midday Bonus: 2x Points"
                description = "Take a break and earn double points on all purchases between 11 AM and 6 PM."
                
            offer_data = {
                'title': title,
                'description': description,
                'type': 'points_multiplier',
                'points_multiplier': multiplier,
                'points_required': 0,  # No points required to activate
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=3),
                'is_active': True,
                'is_ai_generated': True
            }
            
        elif offer_type == 'free_item':
            # Free item based on day of week
            if day_context == 'weekend':
                title = "Weekend Treat on Us"
                description = "Enjoy a complimentary dessert or side item with your purchase this weekend."
            else:
                title = "Weekday Perk: Free Item"
                description = "Brighten your weekday with a free item of your choice with any purchase over $20."
                
            offer_data = {
                'title': title,
                'description': description,
                'type': 'free_item',
                'free_item_description': "Any item up to $10 value",
                'points_required': 300,
                'valid_from': timezone.now(),
                'valid_until': timezone.now() + timedelta(days=5),
                'is_active': True,
                'is_ai_generated': True
            }
        
        return offer_data
    
    @staticmethod
    def predict_churn(wallet_id):
        """
        Predict the likelihood of customer churn.
        
        In production, this would use a trained ML model, but for the prototype
        we use a mock implementation.
        """
        if not settings.AI_SERVICE_ENABLED:
            return None
        
        # In a real implementation, fetch customer data and use ML model
        if settings.AI_SERVICE_MOCK:
            return AIService._mock_predict_churn(wallet_id)
        else:
            # Here would be code to use the real ML model
            pass
    
    @staticmethod
    def _mock_predict_churn(wallet_id):
        """Mock implementation of churn prediction for the prototype."""
        try:
            wallet = CustomerWallet.objects.get(id=wallet_id)
            
            # Calculate days since last activity
            days_since = (timezone.now() - wallet.last_activity).days
            
            # Calculate basic engagement score (inverse of days since activity)
            if days_since <= 7:
                engagement_score = 0.9
            elif days_since <= 30:
                engagement_score = 0.7
            elif days_since <= 90:
                engagement_score = 0.4
            else:
                engagement_score = 0.1
                
            # Adjust based on point balance
            if wallet.points_balance > 1000:
                engagement_score += 0.2
            elif wallet.points_balance < 100:
                engagement_score -= 0.1
                
            # Calculate churn risk (inverse of engagement)
            churn_risk = max(0.0, min(1.0 - engagement_score, 0.95))
            
            # Create and return prediction
            prediction = ChurnPrediction(
                wallet=wallet,
                churn_risk_score=churn_risk,
                days_since_last_activity=days_since,
                engagement_score=engagement_score
            )
            prediction.save()
            
            return prediction
            
        except CustomerWallet.DoesNotExist:
            return None
    
    @staticmethod
    def create_customer_segments(business_id):
        """
        Create customer segments for a business.
        
        In production, this would use clustering algorithms, but for the prototype
        we use a mock implementation.
        """
        if not settings.AI_SERVICE_ENABLED:
            return None
        
        # Mock segments
        segments = [
            {
                'name': 'High Value Customers',
                'description': 'Customers with high lifetime points',
                'segment_type': 'value',
                'criteria': json.dumps({'min_lifetime_points': 5000})
            },
            {
                'name': 'At Risk Customers',
                'description': 'Customers with high churn risk',
                'segment_type': 'churn_risk',
                'criteria': json.dumps({'min_churn_risk': 0.7})
            },
            {
                'name': 'New Customers',
                'description': 'Customers who joined in the last 30 days',
                'segment_type': 'behavioral',
                'criteria': json.dumps({'max_days_since_joined': 30})
            },
            {
                'name': 'Inactive Customers',
                'description': 'Customers with no activity in the last 60 days',
                'segment_type': 'behavioral',
                'criteria': json.dumps({'min_days_since_activity': 60})
            }
        ]
        
        created_segments = []
        for segment_data in segments:
            segment, created = CustomerSegment.objects.get_or_create(
                business_id=business_id,
                name=segment_data['name'],
                defaults={
                    'description': segment_data['description'],
                    'segment_type': segment_data['segment_type'],
                    'criteria': segment_data['criteria'],
                    'is_ai_generated': True
                }
            )
            created_segments.append(segment)
        
        return created_segments
    
    @staticmethod
    def handle_ai_chatbot_query(customer_id, business_id, query):
        """
        Process a customer query through the AI chatbot.
        
        In production, this would call an LLM API, but for the prototype
        we use a mock implementation.
        """
        if not settings.AI_SERVICE_ENABLED:
            return "I'm sorry, the AI chatbot service is currently disabled."
        
        # In a real implementation, process the query with an LLM
        if settings.AI_SERVICE_MOCK:
            return AIService._mock_chatbot_response(customer_id, business_id, query)
        else:
            # Here would be code to call the real AI chatbot service
            pass
    
    @staticmethod
    def _mock_chatbot_response(customer_id, business_id, query):
        """Mock implementation of chatbot for the prototype."""
        query_lower = query.lower()
        
        # Get some basic customer info if possible
        customer_uuid = AIService._parse_uuid(customer_id)
        has_wallet = False
        points_balance = 0
        if customer_uuid:
            try:
                wallet = CustomerWallet.objects.get(customer_id=customer_uuid, business_id=business_id)
                points_balance = wallet.points_balance
                has_wallet = True
            except CustomerWallet.DoesNotExist:
                points_balance = 0
                has_wallet = False
        
        # Simple rule-based responses
        if 'point' in query_lower or 'balance' in query_lower:
            if has_wallet:
                return f"Your current points balance is {points_balance}. Is there anything specific you'd like to know about redeeming these points?"
            else:
                return "You don't have a wallet with this business yet. Would you like to sign up for our loyalty program?"
                
        elif 'redeem' in query_lower or 'reward' in query_lower or 'offer' in query_lower:
            offers = Offer.objects.filter(
                business_id=business_id, 
                is_active=True
            ).order_by('points_required')[:3]
            
            if offers.exists():
                response = "Here are some offers you might be interested in:\n\n"
                for offer in offers:
                    response += f"- {offer.title}: {offer.points_required} points required\n"
                return response
            else:
                return "There are currently no active offers available. Please check back soon!"
                
        elif 'help' in query_lower or 'support' in query_lower or 'assistance' in query_lower:
            return "I'm here to help! You can ask me about your points balance, available rewards, how to earn more points, or any other questions about our loyalty program."
            
        elif 'thank' in query_lower:
            return "You're welcome! Is there anything else I can help you with today?"
            
        else:
            return "I'm still learning how to answer that. In the meantime, you can ask me about your points balance, available rewards, or how to earn more points."