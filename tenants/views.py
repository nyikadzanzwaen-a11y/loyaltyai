from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone

from .models import Business, BusinessConfig
from loyalty.models import LoyaltyTier, Offer, CustomerWallet, WalletTransaction, OfferRedemption
from accounts.models import User
from ai_service.models import CustomerSegment, ChurnPrediction, AIGeneratedOffer
from ai_service.services import AIService

class BusinessRequiredMixin:
    """Mixin that requires a valid business slug in URL and sets tenant context."""
    
    def dispatch(self, request, *args, **kwargs):
        slug = kwargs.get('slug')
        if not slug:
            raise Http404("Business slug not provided")
            
        try:
            self.business = Business.objects.get(slug=slug, is_active=True)
        except Business.DoesNotExist:
            raise Http404("Business not found or inactive")
            
        # Check if user is authorized for this business
        if not request.user.is_authenticated or (
            request.user.is_business_admin and 
            str(request.user.tenant_id) != str(self.business.id)
        ):
            messages.error(request, "You don't have permission to access this business dashboard.")
            return redirect('home')
            
        return super().dispatch(request, *args, **kwargs)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['business'] = self.business
        return context


@method_decorator(login_required, name='dispatch')
class BusinessDashboardView(BusinessRequiredMixin, TemplateView):
    """Main dashboard view for business admins."""
    template_name = 'tenants/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        business = self.business
        
        # Get key metrics
        total_customers = CustomerWallet.objects.filter(business=business).count()
        total_points_issued = WalletTransaction.objects.filter(
            wallet__business=business,
            transaction_type='earn'
        ).aggregate(total=Sum('points'))['total'] or 0
        total_points_redeemed = WalletTransaction.objects.filter(
            wallet__business=business,
            transaction_type='redeem'
        ).aggregate(total=Sum('points'))['total'] or 0
        active_offers = Offer.objects.filter(business=business, is_active=True).count()
        
        # Get recent transactions
        recent_transactions = WalletTransaction.objects.filter(
            wallet__business=business
        ).select_related('wallet__customer').order_by('-created_at')[:10]
        
        # Get at-risk customers
        at_risk_customers = ChurnPrediction.objects.filter(
            wallet__business=business,
            churn_risk_score__gt=0.7
        ).select_related('wallet__customer').order_by('-churn_risk_score')[:5]
        
        # Add to context
        context.update({
            'total_customers': total_customers,
            'total_points_issued': total_points_issued,
            'total_points_redeemed': total_points_redeemed,
            'active_offers': active_offers,
            'recent_transactions': recent_transactions,
            'at_risk_customers': at_risk_customers,
        })
        
        return context


@method_decorator(login_required, name='dispatch')
class OfferListView(BusinessRequiredMixin, ListView):
    """View for listing and managing business offers."""
    template_name = 'tenants/offers.html'
    context_object_name = 'offers'
    paginate_by = 10
    
    def get_queryset(self):
        qs = Offer.objects.filter(business=self.business).order_by('-created_at')
        q = self.request.GET.get('q', '')
        if q:
            q = q.strip()
            if q:
                qs = qs.filter(
                    Q(title__icontains=q) |
                    Q(description__icontains=q) |
                    Q(type__icontains=q)
                )
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['loyalty_tiers'] = LoyaltyTier.objects.filter(business=self.business)
        # Expose current search query and persistent querystring for pagination links
        q = self.request.GET.get('q', '')
        context['q'] = q
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['querystring'] = query_params.urlencode()
        return context


@method_decorator(login_required, name='dispatch')
class CustomerListView(BusinessRequiredMixin, ListView):
    """View for listing and managing customers."""
    template_name = 'tenants/customers.html'
    context_object_name = 'wallets'
    
    def get_queryset(self):
        return CustomerWallet.objects.filter(business=self.business).select_related(
            'customer', 'current_tier'
        ).order_by('-points_balance')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get segments for filtering
        context['segments'] = CustomerSegment.objects.filter(business=self.business)
        
        # Get churn predictions
        wallets_with_predictions = {}
        predictions = ChurnPrediction.objects.filter(
            wallet__business=self.business
        ).select_related('wallet')
        
        for pred in predictions:
            wallets_with_predictions[str(pred.wallet.id)] = pred.churn_risk_score
            
        context['churn_predictions'] = wallets_with_predictions
        
        return context


@method_decorator(login_required, name='dispatch')
class BusinessAnalyticsView(BusinessRequiredMixin, TemplateView):
    """View for business analytics and insights."""
    template_name = 'tenants/analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        business = self.business
        
        # Date ranges for time-based metrics
        now = timezone.now()
        thirty_days_ago = now - timezone.timedelta(days=30)
        ninety_days_ago = now - timezone.timedelta(days=90)
        
        # Points and transactions metrics
        points_data = WalletTransaction.objects.filter(
            wallet__business=business
        ).aggregate(
            total_points_issued=Sum('points', filter=Q(transaction_type='earn')),
            total_points_redeemed=Sum('points', filter=Q(transaction_type='redeem')),
            recent_points_issued=Sum('points', filter=Q(
                transaction_type='earn', 
                created_at__gte=thirty_days_ago
            )),
            recent_points_redeemed=Sum('points', filter=Q(
                transaction_type='redeem', 
                created_at__gte=thirty_days_ago
            )),
        )
        
        # Offer performance metrics
        offer_metrics = OfferRedemption.objects.filter(
            offer__business=business
        ).values('offer_id', 'offer__title').annotate(
            total_redemptions=Count('id'),
            points_used=Sum('points_used')
        ).order_by('-total_redemptions')[:5]
        
        # Customer engagement metrics
        customer_metrics = {
            'total_customers': CustomerWallet.objects.filter(business=business).count(),
            'active_customers': CustomerWallet.objects.filter(
                business=business,
                last_activity__gte=thirty_days_ago
            ).count(),
            'at_risk_customers': ChurnPrediction.objects.filter(
                wallet__business=business,
                churn_risk_score__gt=0.7
            ).count(),
        }
        
        # Add to context
        context.update({
            'points_data': points_data,
            'offer_metrics': offer_metrics,
            'customer_metrics': customer_metrics,
            'thirty_days_ago': thirty_days_ago,
        })
        
        return context


@method_decorator(login_required, name='dispatch')
class BusinessSettingsView(BusinessRequiredMixin, UpdateView):
    """View for business settings and configuration."""
    template_name = 'tenants/settings.html'
    model = Business
    fields = ['name', 'email', 'phone', 'category', 'description', 'logo', 'website', 
              'address', 'city', 'state', 'country', 'postal_code', 
              'point_value', 'points_per_currency']
    
    def get_object(self, queryset=None):
        return self.business
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get business configuration
        try:
            context['config'] = BusinessConfig.objects.get(business=self.business)
        except BusinessConfig.DoesNotExist:
            context['config'] = BusinessConfig(business=self.business)
        
        # Get loyalty tiers
        context['loyalty_tiers'] = LoyaltyTier.objects.filter(business=self.business)
        
        return context
    
    def form_valid(self, form):
        messages.success(self.request, "Business settings updated successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('business_settings', kwargs={'slug': self.business.slug})


class CreateOfferView(BusinessRequiredMixin, CreateView):
    """View for creating new offers."""
    model = Offer
    template_name = 'tenants/offer_form.html'
    fields = ['title', 'description', 'type', 'points_required', 
              'discount_percentage', 'discount_amount', 'points_multiplier', 
              'free_item_description', 'valid_from', 'valid_until', 
              'specific_tier', 'image']
    
    def form_valid(self, form):
        form.instance.business = self.business
        messages.success(self.request, "Offer created successfully.")
        return super().form_valid(form)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['specific_tier'].queryset = LoyaltyTier.objects.filter(business=self.business)
        return form
    
    def get_success_url(self):
        return reverse('business_offers', kwargs={'slug': self.business.slug})


class UpdateOfferView(BusinessRequiredMixin, UpdateView):
    """View for updating offers."""
    model = Offer
    template_name = 'tenants/offer_form.html'
    fields = ['title', 'description', 'type', 'points_required', 
              'discount_percentage', 'discount_amount', 'points_multiplier', 
              'free_item_description', 'is_active', 'valid_from', 'valid_until', 
              'specific_tier', 'image']
    
    def get_queryset(self):
        return Offer.objects.filter(business=self.business)
    
    def form_valid(self, form):
        messages.success(self.request, "Offer updated successfully.")
        return super().form_valid(form)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['specific_tier'].queryset = LoyaltyTier.objects.filter(business=self.business)
        return form
    
    def get_success_url(self):
        return reverse('business_offers', kwargs={'slug': self.business.slug})


class DeleteOfferView(BusinessRequiredMixin, DeleteView):
    """View for deleting offers."""
    model = Offer
    template_name = 'tenants/offer_confirm_delete.html'
    
    def get_queryset(self):
        return Offer.objects.filter(business=self.business)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, "Offer deleted successfully.")
        return super().delete(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse('business_offers', kwargs={'slug': self.business.slug})


class GenerateAIOfferView(BusinessRequiredMixin, TemplateView):
    """View for generating AI offers."""
    template_name = 'tenants/ai_offer_form.html'
    
    def post(self, request, *args, **kwargs):
        customer_id = request.POST.get('customer_id')
        context = {
            'time_of_day': request.POST.get('time_of_day', 'day'),
            'day_of_week': request.POST.get('day_of_week', 'weekday'),
        }
        
        # Generate offer data
        offer_data = AIService.generate_personalized_offer(
            customer_id=customer_id,
            business_id=self.business.id,
            context=context
        )
        
        if not offer_data:
            return JsonResponse({'error': 'Failed to generate offer'}, status=400)
        
        # Create the offer
        offer = Offer.objects.create(
            business=self.business,
            **offer_data
        )
        
        # Create AI offer metadata
        target_segment_id = request.POST.get('target_segment')
        
        ai_offer = AIGeneratedOffer.objects.create(
            offer=offer,
            target_segment_id=target_segment_id if target_segment_id else None,
            context_factors=context
        )
        
        return JsonResponse({
            'success': True,
            'offer_id': str(offer.id),
            'title': offer.title,
            'description': offer.description
        })


def create_customer_segments_view(request, slug):
    """View for creating customer segments."""
    if not request.user.is_authenticated or not request.user.is_business_admin:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        business = Business.objects.get(slug=slug)
        
        # Check if user belongs to this business
        if str(request.user.tenant_id) != str(business.id):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        # Create segments
        segments = AIService.create_customer_segments(business.id)
        
        if not segments:
            return JsonResponse({'error': 'Failed to create segments'}, status=400)
        
        return JsonResponse({
            'success': True,
            'segments_created': len(segments)
        })
        
    except Business.DoesNotExist:
        return JsonResponse({'error': 'Business not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)