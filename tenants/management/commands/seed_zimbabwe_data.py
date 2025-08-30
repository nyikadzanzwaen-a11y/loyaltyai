import random
import string
from datetime import timedelta, date

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from django.db import transaction
from django.conf import settings

from accounts.models import User, UserProfile
from tenants.models import Business, BusinessConfig
from loyalty.models import (
    LoyaltyTier,
    Offer,
    CustomerWallet,
    WalletTransaction,
    OfferRedemption,
)
from ai_service.models import (
    CustomerSegment,
    CustomerSegmentMembership,
    AIGeneratedOffer,
    ChurnPrediction,
    ChatConversation,
    ChatMessage,
)


class Command(BaseCommand):
    help = "Seed realistic Zimbabwean (Shona + local context) demo data across the platform."

    def add_arguments(self, parser):
        parser.add_argument("--businesses", type=int, default=6, help="Number of businesses to create")
        parser.add_argument("--customers", type=int, default=60, help="Number of customer users to create")
        parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")

    def handle(self, *args, **options):
        random.seed(options["seed"])
        businesses_target = options["businesses"]
        customers_target = options["customers"]

        self.stdout.write("Seeding Zimbabwean demo data...")
        with transaction.atomic():
            customers = self._ensure_customers(customers_target)
            businesses = self._ensure_businesses(businesses_target)

            # Link customers to businesses via wallets, seed transactions and tiers
            for biz in businesses:
                self._ensure_config(biz)
                tiers = self._ensure_tiers(biz)
                offers = self._ensure_offers(biz, tiers)
                wallets = self._ensure_wallets(biz, customers, tiers)
                self._seed_transactions_and_redemptions(biz, wallets, offers)
                segments = self._ensure_segments(biz)
                self._ensure_segment_memberships(segments, wallets)
                self._ensure_ai_metadata(offers, segments)
                self._ensure_churn_predictions(wallets)
                self._ensure_sample_chats(biz, wallets)

        # Post-seed summary
        self.stdout.write("\nAccounts you can use to log in:")
        for biz in businesses:
            admin = User.objects.filter(is_business_admin=True, tenant_id=biz.id).first()
            if admin:
                self.stdout.write(f"- {biz.name} admin: {admin.email} / AdminPass!123")
        if customers:
            self.stdout.write(f"- Sample customer: {customers[0].email} / Passw0rd!")

        self.stdout.write(self.style.SUCCESS("Seeding complete."))

    # --------------------------
    # Static data pools (no Faker)
    # --------------------------
    male_first_names = [
        "Tafadzwa", "Tawanda", "Kudakwashe", "Simbarashe", "Takudzwa", "Tatenda", "Munyaradzi",
        "Tendai", "Farai", "Panashe", "Admire", "Blessing", "Kuda",
    ]
    female_first_names = [
        "Rutendo", "Nyasha", "Chipo", "Tariro", "Ruvimbo", "Wadzanai", "Rudo", "Tadiwa",
        "Vimbai", "Shamiso", "Netsai", "Chiedza", "Anesu",
    ]
    surnames = [
        "Moyo", "Ndlovu", "Dube", "Sibanda", "Nyathi", "Mpofu", "Mlambo", "Gumbo", "Hove",
        "Chibanda", "Chirima", "Makoni", "Mutasa", "Mandaza", "Muzenda", "Zvobgo", "Karimanzira",
        "Chiwenga", "Matiza", "Gutu",
    ]
    streets = [
        "Samora Machel Ave", "Julius Nyerere Way", "Leopold Takawira St", "Jason Moyo St",
        "Nelson Mandela Ave", "Kwame Nkrumah Ave", "Robert Mugabe Rd", "Herbert Chitepo Ave",
        "Khami Rd", "Airport Rd", "Lomagundi Rd",
    ]
    cities = [
        "Harare", "Bulawayo", "Mutare", "Gweru", "Masvingo", "Kwekwe", "Chitungwiza",
        "Bindura", "Chinhoyi", "Kadoma", "Marondera", "Victoria Falls",
    ]
    categories = [
        ("retail", "Retail"),
        ("restaurant", "Restaurant"),
        ("hospitality", "Hospitality"),
        ("beauty", "Beauty & Wellness"),
        ("entertainment", "Entertainment"),
        ("travel", "Travel"),
    ]

    sample_businesses = [
        {"name": "Mbare Fresh Market", "category": "retail"},
        {"name": "Highfield Grill & Dine", "category": "restaurant"},
        {"name": "Victoria Falls Adventures", "category": "travel"},
        {"name": "Avondale Beauty Spa", "category": "beauty"},
        {"name": "Bulawayo Entertainment Hub", "category": "entertainment"},
        {"name": "Mutare Home & Retail", "category": "retail"},
        {"name": "Kariba Breeze Tours", "category": "hospitality"},
        {"name": "Gweru Fitness & Wellness", "category": "beauty"},
    ]

    # --------------------------
    # Helpers
    # --------------------------
    def _rand_phone(self):
        # Zimbabwe mobile formats (approx): 071X/073X/077X/078X... We'll simulate 0772 123 456
        prefix = random.choice(["071", "073", "077", "078"])
        return f"+263 {prefix}{random.randint(0,9)} {random.randint(100,999)} {random.randint(100,999)}"

    def _rand_address(self):
        number = random.randint(1, 999)
        street = random.choice(self.streets)
        city = random.choice(self.cities)
        return number, street, city

    def _unique_email(self, base_local: str, domain: str = "mail.co.zw"):
        # Ensure unique emails by adding suffix if necessary
        base_local = base_local.lower().replace(" ", ".")
        candidate = f"{base_local}@{domain}"
        counter = 1
        while User.objects.filter(email=candidate).exists():
            candidate = f"{base_local}{counter}@{domain}"
            counter += 1
        return candidate

    def _safe_slug(self, name: str) -> str:
        base = slugify(name)
        slug = base or "biz"
        counter = 1
        while Business.objects.filter(slug=slug).exists():
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    def _random_name(self):
        if random.random() < 0.5:
            first = random.choice(self.male_first_names)
        else:
            first = random.choice(self.female_first_names)
        last = random.choice(self.surnames)
        return first, last

    # --------------------------
    # Ensure core data
    # --------------------------
    def _ensure_customers(self, count):
        existing_customers = list(User.objects.filter(is_customer=True, is_business_admin=False))
        to_create = max(0, count - len(existing_customers))
        created = []
        default_password = "Passw0rd!"

        for _ in range(to_create):
            first, last = self._random_name()
            email_local = f"{first}.{last}"
            email = self._unique_email(email_local)
            user = User(email=email, username=email, is_customer=True, is_business_admin=False, is_platform_admin=False)
            user.set_password(default_password)
            user.phone = self._rand_phone()
            user.save()

            number, street, city = self._rand_address()
            UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "bio": random.choice([
                        "Loyal customer who loves value deals",
                        "Enjoys local cuisine and outdoor adventures",
                        "Prefers quick redemptions and weekend promos",
                        "Holiday shopper and travel enthusiast",
                    ]),
                    "date_of_birth": date.fromordinal(random.randint(date(1975, 1, 1).toordinal(), date(2004, 12, 31).toordinal())),
                    "address": f"{number} {street}",
                    "city": city,
                    "country": "Zimbabwe",
                }
            )
            created.append(user)

        self.stdout.write(f"Customers existing={len(existing_customers)} created={len(created)} total={len(existing_customers)+len(created)}")
        return existing_customers + created

    def _ensure_businesses(self, count):
        created = []
        all_biz = list(Business.objects.all())
        if len(all_biz) >= count:
            self.stdout.write(f"Businesses existing={len(all_biz)}; target={count}. Skipping creation.")
            return all_biz

        # Create from curated list first, then random if needed
        pool = list(self.sample_businesses)
        while len(all_biz) + len(created) < count:
            if pool:
                sample = pool.pop(0)
                name = sample["name"]
                category = sample["category"]
            else:
                name = f"{random.choice(['Zimbabwe', 'Kariba', 'Harare', 'Matobo', 'Zambezi'])} {random.choice(['Retail', 'Foods', 'Tours', 'Beauty', 'Events'])}"
                category = random.choice([c for c, _ in self.categories])

            slug = self._safe_slug(name)
            email = f"admin@{slug}.co.zw"
            phone = self._rand_phone()
            website = f"https://{slug}.co.zw"

            biz = Business.objects.create(
                name=name,
                slug=slug,
                email=email,
                phone=phone,
                category=category,
                description=random.choice([
                    "Leading local brand serving the community.",
                    "Premium experiences with a Zimbabwean touch.",
                    "Affordable deals and quality service.",
                    "Authentic tastes and vibrant culture.",
                ]),
                website=website,
                address=f"{random.randint(10, 999)} {random.choice(self.streets)}",
                city=random.choice(self.cities),
                state="",
                country="Zimbabwe",
                postal_code=str(random.randint(1000, 9999)),
            )

            # Create a business admin
            admin_email = self._unique_email(f"{slug}.admin", domain="co.zw")
            admin = User.objects.create(
                email=admin_email,
                username=admin_email,
                is_customer=False,
                is_business_admin=True,
                is_platform_admin=False,
                tenant_id=biz.id,
                phone=self._rand_phone(),
            )
            admin.set_password("AdminPass!123")
            admin.save()
            UserProfile.objects.get_or_create(user=admin, defaults={"city": biz.city, "country": "Zimbabwe"})

            # Log admin credential for convenience
            self.stdout.write(f"Admin created for {biz.name}: {admin_email} / AdminPass!123")

            created.append(biz)

        self.stdout.write(f"Businesses created={len(created)} total={len(all_biz)+len(created)}")
        return all_biz + created

    def _ensure_config(self, biz: Business):
        BusinessConfig.objects.get_or_create(
            business=biz,
            defaults={
                "primary_color": random.choice(["#0EA5E9", "#2563EB", "#7C3AED", "#059669"]),
                "secondary_color": random.choice(["#6B7280", "#334155", "#475569", "#4B5563"]),
                "accent_color": random.choice(["#F59E0B", "#EF4444", "#10B981"]),
            },
        )

    def _ensure_tiers(self, biz: Business):
        tiers = []
        spec = [
            ("Bronze", 0, 1.00),
            ("Silver", 2000, 1.25),
            ("Gold", 8000, 1.50),
        ]
        for name, min_pts, mult in spec:
            tier, _ = LoyaltyTier.objects.get_or_create(
                business=biz,
                name=name,
                defaults={
                    "minimum_points": min_pts,
                    "point_multiplier": mult,
                    "special_offers": name != "Bronze",
                    "priority_support": name == "Gold",
                    "exclusive_events": name == "Gold",
                    "color_code": random.choice(["#CD7F32", "#C0C0C0", "#FFD700"]),
                },
            )
            tiers.append(tier)
        return tiers

    def _ensure_offers(self, biz: Business, tiers):
        offers = list(biz.offers.all())
        needed = max(0, 5 - len(offers))
        if needed == 0:
            return offers
        catalog = [
            {
                "title": "10% Off Groceries",
                "type": "discount",
                "description": "Save 10% on your basket this week at our Harare stores.",
                "discount_percentage": 10,
            },
            {
                "title": "Buy 1 Get 1 Free",
                "type": "free_item",
                "description": "BOGO on selected local products.",
                "free_item_description": "Buy sadza meal, get free relish",
            },
            {
                "title": "2x Points Weekend",
                "type": "points_multiplier",
                "description": "Earn double points on purchases this weekend.",
                "points_multiplier": 2.0,
            },
            {
                "title": "Holiday Special $5 Off",
                "type": "discount",
                "description": "Holiday discount for our loyal customers.",
                "discount_amount": 5,
            },
            {
                "title": "VIP Night Event",
                "type": "special_event",
                "description": "Exclusive event for Silver and Gold members.",
                "specific_tier": next((t for t in tiers if t.name != "Bronze"), None),
            },
        ]
        random.shuffle(catalog)
        now = timezone.now()
        created = []
        for spec in catalog[:needed]:
            valid_from = now - timedelta(days=random.randint(0, 20))
            valid_until = now + timedelta(days=random.randint(20, 120))
            payload = {
                "business": biz,
                "title": spec["title"],
                "description": spec["description"],
                "type": spec["type"],
                "points_required": random.choice([0, 0, 500, 1000]),
                "discount_percentage": spec.get("discount_percentage"),
                "discount_amount": spec.get("discount_amount"),
                "points_multiplier": spec.get("points_multiplier"),
                "free_item_description": spec.get("free_item_description"),
                "is_active": True,
                "valid_from": valid_from,
                "valid_until": valid_until,
                "specific_tier": spec.get("specific_tier"),
                "is_ai_generated": random.random() < 0.35,
            }
            offer = Offer.objects.create(**payload)
            created.append(offer)
        return offers + created

    def _ensure_wallets(self, biz: Business, customers, tiers):
        # Assign a subset of customers to this business
        subset = random.sample(customers, k=max(10, len(customers) // 3))
        wallets = []
        for user in subset:
            wallet, created = CustomerWallet.objects.get_or_create(customer=user, business=biz)
            if created:
                # Initialize with some points and tier
                base_points = random.randint(0, 12000)
                wallet.points_balance = 0
                wallet.lifetime_points = 0
                wallet.current_tier = None
                wallet.last_activity = timezone.now() - timedelta(days=random.randint(0, 120))
                wallet.save()
                if base_points:
                    wallet.add_points(base_points, transaction_type="earn", description="Initial seed points")
            wallets.append(wallet)
        return wallets

    def _seed_transactions_and_redemptions(self, biz: Business, wallets, offers):
        for wallet in wallets:
            # Additional earn transactions
            for _ in range(random.randint(1, 5)):
                pts = random.choice([50, 100, 150, 200, 250, 500])
                wallet.add_points(pts, transaction_type="earn", description="Purchase points")

            # Occasional redemption
            if wallet.points_balance >= 500 and offers:
                # Choose an offer requiring points if available
                point_offers = [o for o in offers if (o.points_required or 0) > 0] or offers
                offer = random.choice(point_offers)
                cost = offer.points_required or random.choice([500, 1000])
                if wallet.points_balance >= cost:
                    try:
                        wallet.deduct_points(cost, transaction_type="redeem", description=f"Redeemed: {offer.title}")
                        redemption = OfferRedemption.objects.create(
                            wallet=wallet,
                            offer=offer,
                            points_used=cost,
                            redemption_code="RD" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)),
                            is_used=random.random() < 0.7,
                            # used_at will be set below to ensure it's not before redeemed_at
                            used_at=None,
                        )
                        if redemption.is_used:
                            # Ensure used_at is on/after redeemed_at
                            redemption.used_at = redemption.redeemed_at + timedelta(days=random.randint(0, 30))
                            redemption.save(update_fields=["used_at"]) 
                    except ValueError:
                        pass

    def _ensure_segments(self, biz: Business):
        segs = []
        spec = [
            ("High Value Customers", "value", "Lifetime points above median"),
            ("At Risk", "churn_risk", "Low recent activity"),
            ("Frequent Shoppers", "behavioral", "Many small purchases"),
        ]
        for name, seg_type, desc in spec:
            seg, _ = CustomerSegment.objects.get_or_create(
                business=biz,
                name=name,
                defaults={"segment_type": seg_type, "description": desc, "criteria": "{}", "size": 0},
            )
            segs.append(seg)
        return segs

    def _ensure_segment_memberships(self, segments, wallets):
        if not wallets:
            return
        # Derive simple metrics from wallets
        points_list = [w.lifetime_points for w in wallets]
        median = sorted(points_list)[len(points_list) // 2]
        now = timezone.now()

        for w in wallets:
            # High Value
            if w.lifetime_points >= median:
                self._add_membership(segments, "High Value Customers", w.customer, score=min(1.0, 0.7 + w.lifetime_points / (median * 3 + 1)))
            # At Risk (inactive > 45 days)
            if (now - (w.last_activity or now)).days > 45:
                self._add_membership(segments, "At Risk", w.customer, score=random.uniform(0.6, 0.95))
            # Frequent Shoppers (many transactions)
            if w.transactions.count() >= 6:
                self._add_membership(segments, "Frequent Shoppers", w.customer, score=random.uniform(0.6, 0.95))

        # Update sizes
        for seg in segments:
            seg.size = seg.memberships.count()
            seg.avg_spend = None
            seg.avg_points = None
            seg.save()

    def _add_membership(self, segments, name, customer, score):
        seg = next((s for s in segments if s.name == name), None)
        if not seg:
            return
        CustomerSegmentMembership.objects.get_or_create(segment=seg, customer=customer, defaults={"score": score})

    def _ensure_ai_metadata(self, offers, segments):
        if not offers or not segments:
            return
        for offer in offers:
            if offer.is_ai_generated:
                target_seg = random.choice(segments)
                AIGeneratedOffer.objects.get_or_create(
                    offer=offer,
                    defaults={
                        "target_segment": target_seg,
                        "context_factors": "{}",
                        "impressions": random.randint(100, 5000),
                        "clicks": random.randint(10, 800),
                        "redemptions": random.randint(5, 300),
                        "is_test_variant": random.random() < 0.2,
                    },
                )

    def _ensure_churn_predictions(self, wallets):
        for w in wallets:
            if random.random() < 0.4:
                ChurnPrediction.objects.get_or_create(
                    wallet=w,
                    defaults={
                        "churn_risk_score": round(random.uniform(0.05, 0.85), 2),
                        "days_since_last_activity": (timezone.now() - (w.last_activity or timezone.now())).days,
                        "engagement_score": round(random.uniform(0.2, 0.95), 2),
                    },
                )

    def _ensure_sample_chats(self, biz: Business, wallets):
        participants = [w.customer for w in wallets]
        if not participants:
            return
        for _ in range(random.randint(1, 4)):
            customer = random.choice(participants)
            convo = ChatConversation.objects.create(customer=customer, business=biz)
            # 3-5 messages
            messages = [
                ("customer", random.choice([
                    "Maswera sei? Do you have any specials today?",
                    "How many points do I need to redeem the offer?",
                    "Ndingawana rairo re loyalty tiers here?",
                ])),
                ("ai", random.choice([
                    "Hello! Yes, we have 2x points this weekend.",
                    "You need 500 points for that reward.",
                    "Sure, Bronze starts at 0 points, Silver at 2000, and Gold at 8000.",
                ])),
                ("customer", random.choice([
                    "Ndatenda! Will pass by this afternoon.",
                    "Great, ndatonzwisisa.",
                    "Thanks! Do you deliver to Avondale?",
                ])),
            ]
            # Maybe a business message
            if random.random() < 0.5:
                messages.append(("business", random.choice([
                    "Tinokutendai nerutsigiro! See you soon.",
                    "We do deliver within Harare for orders over $20.",
                ])))

            for mtype, content in messages:
                ChatMessage.objects.create(conversation=convo, message_type=mtype, content=content)
