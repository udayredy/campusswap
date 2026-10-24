import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Max, Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import Program

from .forms import ListingForm, MessageForm, ReportForm, ReviewForm, SearchForm
from .models import Course, Favourite, Listing, ListingPhoto, Message, Report, Review, normalize_course_code
from .utils import member_required, recently_viewed_ids, remember_viewed

User = get_user_model()

CARD_QS = Listing.objects.select_related("course", "seller").prefetch_related(
    Prefetch("photos", queryset=ListingPhoto.objects.order_by("position", "id"))
)


def _fav_ids(user):
    if user.is_authenticated:
        return set(user.favourites.values_list("listing_id", flat=True))
    return set()


def _recent(request, exclude=None):
    ids = recently_viewed_ids(request, exclude=exclude)
    if not ids:
        return []
    found = {l.pk: l for l in CARD_QS.visible().filter(pk__in=ids)}
    return [found[i] for i in ids if i in found]


# ---------------------------------------------------------------- public pages
HOW_IT_WORKS = [
    ("bi-person-plus", "Register / Log in", "Free with your student email"),
    ("bi-search", "Browse & search", "By keyword, course code or ISBN"),
    ("bi-card-text", "View details", "Photos, condition, seller rating"),
    ("bi-plus-circle", "Post a listing", "Up to 5 photos in minutes"),
    ("bi-chat-heart", "Contact / favourite", "Message the seller or save it"),
]


def home(request):
    latest = CARD_QS.active()[:8]
    for_you = []
    program_label = None
    if request.user.is_authenticated and getattr(request.user, "profile", None) and request.user.profile.program:
        program = request.user.profile.program
        program_label = request.user.profile.get_program_display()
        for_you = CARD_QS.active().filter(course__program=program).exclude(seller=request.user)[:4]
    popular_courses = (
        Course.objects.annotate(n=Count("listings", filter=Q(listings__status="AVAILABLE", listings__is_hidden=False)))
        .filter(n__gt=0)
        .order_by("-n", "code")[:6]
    )
    stats = {
        "listings": Listing.objects.active().count(),
        "students": User.objects.filter(is_active=True, is_staff=False).count(),
        "courses": Course.objects.count(),
    }
    return render(
        request,
        "market/home.html",
        {
            "latest": latest,
            "for_you": for_you,
            "program_label": program_label,
            "popular_courses": popular_courses,
            "stats": stats,
            "recent": _recent(request),
            "fav_ids": _fav_ids(request.user),
            "categories": [(v, l, Listing.CATEGORY_ICONS[v]) for v, l in Listing.Category.choices],
            "steps": HOW_IT_WORKS,
        },
    )


GUEST_MEMBER_ROWS = [
    ("Browse & search listings (keyword, course code, ISBN)", True),
    ("Filter by category, condition, price · sort results", True),
    ("Course Book Finder", True),
    ("View item details, photos & seller rating", True),
    ("Seller public profiles", True),
    ("Recently viewed strip", True),
    ("Post a listing with photos", False),
    ("Edit, mark sold or delete own listings", False),
    ("Message sellers & inbox", False),
    ("Save favourites", False),
    ("Rate & review sellers", False),
    ("Report a listing", False),
    ("Personalised picks for your program", False),
]


def credits(request):
    from . import seed_catalog as cat

    books = [
        {"title": b[2], "authors": b[3], "isbn": b[4], "ol": f"https://openlibrary.org/books/{b[6]}", "cover": cat.cover_url(b[5], "S")}
        for b in cat.BOOKS
    ]
    items = [
        {"title": it[4], "file": it[1], "page": cat.commons_page(it[1]), "license": it[9], "author": it[10] or "Unknown / public domain", "license_url": it[11]}
        for it in cat.ITEMS
    ]
    return render(request, "market/credits.html", {"books": books, "items": items})


def guest_vs_member(request):
    return render(request, "market/guest_vs_member.html", {"rows": GUEST_MEMBER_ROWS})


def browse(request):
    # Remember the last sort order so students don't have to keep re-picking it.
    params = request.GET.copy()
    if "sort" not in params and request.session.get("last_sort"):
        params["sort"] = request.session["last_sort"]
    form = SearchForm(params)
    qs = CARD_QS.active()
    active_filters = []

    if form.is_valid():
        d = form.cleaned_data
        q = d.get("q", "").strip()
        if q:
            terms = Q(title__icontains=q) | Q(description__icontains=q) | Q(course__name__icontains=q)
            terms |= Q(course__code__icontains=normalize_course_code(q))
            digits = re.sub(r"[\s-]", "", q)
            if digits.isdigit() and len(digits) >= 4:
                terms |= Q(isbn__icontains=digits) | Q(isbn__icontains=q)
            qs = qs.filter(terms)
            active_filters.append(("q", f"“{q}”"))
        if d.get("category"):
            qs = qs.filter(category=d["category"])
            active_filters.append(("category", dict(Listing.Category.choices)[d["category"]]))
        if d.get("condition"):
            qs = qs.filter(condition=d["condition"])
            active_filters.append(("condition", dict(Listing.Condition.choices)[d["condition"]]))
        if d.get("min_price") is not None:
            qs = qs.filter(price__gte=d["min_price"])
            active_filters.append(("min_price", f"≥ ${d['min_price']:g}"))
        if d.get("max_price") is not None:
            qs = qs.filter(price__lte=d["max_price"])
            active_filters.append(("max_price", f"≤ ${d['max_price']:g}"))
        sort = d.get("sort") or "newest"
        if d.get("sort"):
            request.session["last_sort"] = sort
    else:
        sort = "newest"
        messages.warning(request, "Some filters weren't valid and were ignored.")

    order = {"newest": ["-created_at"], "price_asc": ["price", "-created_at"], "price_desc": ["-price", "-created_at"]}[sort]
    qs = qs.order_by(*order)

    page = Paginator(qs, settings.LISTINGS_PER_PAGE).get_page(request.GET.get("page"))
    request.session["last_browse_qs"] = request.GET.urlencode()
    return render(
        request,
        "market/browse.html",
        {
            "form": form,
            "page": page,
            "active_filters": active_filters,
            "sort": sort,
            "fav_ids": _fav_ids(request.user),
            "recent": _recent(request),
        },
    )


def listing_detail(request, pk):
    listing = get_object_or_404(CARD_QS, pk=pk)
    is_owner = request.user.is_authenticated and request.user == listing.seller
    if listing.is_hidden and not (is_owner or request.user.is_staff):
        raise Http404("This listing is unavailable.")

    if not is_owner:
        Listing.objects.filter(pk=pk).update(view_count=F("view_count") + 1)
    remember_viewed(request, listing.pk)

    ctx = {
        "listing": listing,
        "photos": list(listing.photos.all()),
        "is_owner": is_owner,
        "seller_rating": listing.seller.profile.rating_summary(),
        "reviews": listing.reviews.select_related("reviewer")[:10],
        "related": CARD_QS.active().filter(course=listing.course).exclude(pk=pk)[:4] if listing.course else [],
        "recent": _recent(request, exclude=listing.pk),
        "fav_ids": _fav_ids(request.user),
        "back_qs": request.session.get("last_browse_qs", ""),
    }
    if request.user.is_authenticated and not is_owner:
        has_talked = Message.objects.filter(listing=listing, sender=request.user).exists()
        my_review = listing.reviews.filter(reviewer=request.user).first()
        ctx.update(
            {
                "message_form": MessageForm(),
                "has_talked": has_talked,
                "my_review": my_review,
                "review_form": ReviewForm() if has_talked and not my_review else None,
                "already_reported": listing.reports.filter(reporter=request.user).exists(),
            }
        )
    return render(request, "market/listing_detail.html", ctx)


# ---------------------------------------------------------------- course finder
def course_finder(request):
    program = request.GET.get("program", "")
    courses = Course.objects.annotate(
        n=Count("listings", filter=Q(listings__status="AVAILABLE", listings__is_hidden=False))
    )
    if program in Program.values:
        courses = courses.filter(program=program)
    else:
        program = ""
    q = request.GET.get("q", "").strip()
    if q:
        courses = courses.filter(Q(code__icontains=normalize_course_code(q)) | Q(name__icontains=q))
    return render(
        request,
        "market/course_finder.html",
        {"courses": courses, "programs": Program.choices, "program": program, "q": q},
    )


def course_detail(request, pk):
    course = get_object_or_404(Course, pk=pk)
    listings = CARD_QS.active().filter(course=course).order_by("price")
    return render(request, "market/course_detail.html", {"course": course, "listings": listings, "fav_ids": _fav_ids(request.user)})


# ---------------------------------------------------------------- selling (members)
def _owned_listing_or_404(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    if listing.seller != request.user:
        raise Http404  # don't reveal that someone else's listing exists for editing
    return listing


def _save_photos(listing, files):
    start = listing.photos.aggregate(m=Max("position"))["m"]
    start = -1 if start is None else start
    for i, f in enumerate(files, start=start + 1):
        ListingPhoto.objects.create(listing=listing, image=f, position=i)


def _photo_ctx(existing):
    return {"photo_slots": max(settings.MAX_LISTING_PHOTOS - existing, 0), "max_mb": settings.MAX_PHOTO_MB}


@member_required("post a listing")
def listing_create(request):
    form = ListingForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.save()
            _save_photos(listing, form.cleaned_data["photos"])
        messages.success(request, "Your listing is live! Share the link with classmates.")
        return redirect(listing)
    return render(
        request, "market/listing_form.html", {"form": form, "courses": Course.objects.all(), "mode": "create", **_photo_ctx(0)}
    )


@member_required("edit listings")
def listing_edit(request, pk):
    listing = _owned_listing_or_404(request, pk)
    form = ListingForm(request.POST or None, request.FILES or None, instance=listing)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            _save_photos(listing, form.cleaned_data["photos"])
        messages.success(request, "Listing updated.")
        return redirect(listing)
    return render(
        request,
        "market/listing_form.html",
        {"form": form, "courses": Course.objects.all(), "mode": "edit", "listing": listing, "photos": listing.photos.all(), **_photo_ctx(listing.photos.count())},
    )


@member_required("delete listings")
def listing_delete(request, pk):
    listing = _owned_listing_or_404(request, pk)
    if request.method == "POST":
        title = listing.title
        for p in listing.photos.all():
            p.image.delete(save=False)
        listing.delete()
        messages.success(request, f"“{title}” was deleted.")
        return redirect("market:my_listings")
    return render(request, "market/listing_confirm_delete.html", {"listing": listing})


@require_POST
@member_required("manage listings")
def listing_toggle_sold(request, pk):
    listing = _owned_listing_or_404(request, pk)
    listing.status = Listing.Status.AVAILABLE if listing.is_sold else Listing.Status.SOLD
    listing.save(update_fields=["status", "updated_at"])
    messages.success(request, "Marked as sold – nice!" if listing.is_sold else "Listing is available again.")
    return redirect(request.POST.get("next") or listing.get_absolute_url())


@require_POST
@member_required("manage photos")
def photo_delete(request, pk):
    photo = get_object_or_404(ListingPhoto, pk=pk)
    if photo.listing.seller != request.user:
        raise Http404
    listing = photo.listing
    photo.image.delete(save=False)
    photo.delete()
    messages.success(request, "Photo removed.")
    return redirect("market:listing_edit", pk=listing.pk)


@member_required("see your listings")
def my_listings(request):
    mine = CARD_QS.filter(seller=request.user).annotate(
        fav_n=Count("favourited_by", distinct=True), msg_n=Count("messages", distinct=True)
    )
    tab = request.GET.get("tab", "active")
    if tab == "sold":
        shown = mine.filter(status=Listing.Status.SOLD)
    else:
        tab = "active"
        shown = mine.filter(status=Listing.Status.AVAILABLE)
    counts = {
        "active": mine.filter(status=Listing.Status.AVAILABLE).count(),
        "sold": mine.filter(status=Listing.Status.SOLD).count(),
    }
    return render(request, "market/my_listings.html", {"listings": shown, "tab": tab, "counts": counts})


# ---------------------------------------------------------------- favourites
@require_POST
@member_required("save favourites")
def favourite_toggle(request, pk):
    listing = get_object_or_404(Listing.objects.visible(), pk=pk)
    fav, created = Favourite.objects.get_or_create(user=request.user, listing=listing)
    if not created:
        fav.delete()
    saved = created
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"saved": saved, "count": request.user.favourites.count()})
    messages.success(request, "Saved to My Favourites." if saved else "Removed from favourites.")
    return redirect(request.POST.get("next") or listing.get_absolute_url())


@member_required("see your favourites")
def favourites(request):
    favs = CARD_QS.visible().filter(favourited_by__user=request.user).order_by("-favourited_by__created_at")
    return render(request, "market/favourites.html", {"listings": favs, "fav_ids": _fav_ids(request.user)})


# ---------------------------------------------------------------- messaging
@member_required("see your messages")
def inbox(request):
    me = request.user
    msgs = (
        Message.objects.filter(Q(sender=me) | Q(recipient=me))
        .select_related("listing", "sender", "recipient", "sender__profile", "recipient__profile")
        .prefetch_related("listing__photos")
        .order_by("-sent_at")
    )
    threads = {}
    for m in msgs:
        other = m.recipient if m.sender_id == me.id else m.sender
        key = (m.listing_id, other.id)
        if key not in threads:
            threads[key] = {"listing": m.listing, "other": other, "last": m, "unread": 0}
        if m.recipient_id == me.id and not m.is_read:
            threads[key]["unread"] += 1
    return render(request, "market/inbox.html", {"threads": list(threads.values())})


@member_required("message sellers")
def conversation(request, listing_pk, user_pk):
    listing = get_object_or_404(Listing, pk=listing_pk)
    other = get_object_or_404(User, pk=user_pk)
    me = request.user
    if other == me:
        messages.info(request, "That's your own listing – buyers' messages will show up in your inbox.")
        return redirect(listing)
    # One side of every conversation must be the seller.
    if me != listing.seller and other != listing.seller:
        raise PermissionDenied("You can only message the seller of this listing.")
    thread = Message.objects.filter(listing=listing).filter(
        Q(sender=me, recipient=other) | Q(sender=other, recipient=me)
    ).select_related("sender")
    if listing.is_hidden and not thread.exists() and me != listing.seller:
        raise Http404

    form = MessageForm(request.POST or None)
    if request.method == "POST":
        if listing.is_sold and me != listing.seller and not thread.exists():
            messages.warning(request, "This item has already been sold.")
            return redirect(listing)
        if form.is_valid():
            Message.objects.create(listing=listing, sender=me, recipient=other, body=form.cleaned_data["body"])
            if request.POST.get("from") == "listing":
                messages.success(request, f"Message sent to {other.username}. Replies appear in your Inbox.")
            return redirect("market:conversation", listing_pk=listing.pk, user_pk=other.pk)
    thread.filter(recipient=me, is_read=False).update(is_read=True)
    return render(request, "market/conversation.html", {"listing": listing, "other": other, "thread": thread, "form": form})


# ---------------------------------------------------------------- reviews & reports
@require_POST
@member_required("leave reviews")
def review_create(request, pk):
    listing = get_object_or_404(Listing.objects.visible(), pk=pk)
    if listing.seller == request.user:
        messages.error(request, "You can't review your own listing.")
        return redirect(listing)
    if not Message.objects.filter(listing=listing, sender=request.user).exists():
        messages.error(request, "Message the seller about this item before leaving a review.")
        return redirect(listing)
    form = ReviewForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                Review.objects.create(listing=listing, reviewer=request.user, **form.cleaned_data)
            messages.success(request, "Thanks! Your review helps other students trade with confidence.")
        except IntegrityError:
            messages.info(request, "You've already reviewed this item.")
    else:
        messages.error(request, "Please pick a star rating from 1 to 5.")
    return redirect(listing.get_absolute_url() + "#reviews")


@member_required("report listings")
def report_create(request, pk):
    listing = get_object_or_404(Listing.objects.visible(), pk=pk)
    if listing.seller == request.user:
        messages.info(request, "You can't report your own listing – edit or delete it instead.")
        return redirect(listing)
    if Report.objects.filter(listing=listing, reporter=request.user).exists():
        messages.info(request, "You've already reported this listing. A moderator will review it.")
        return redirect(listing)
    form = ReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.listing, report.reporter = listing, request.user
        report.save()
        messages.success(request, "Thanks for flagging this. Our moderators will take a look.")
        listing.refresh_from_db()
        return redirect("market:home" if listing.is_hidden else listing.get_absolute_url())
    return render(request, "market/report_form.html", {"form": form, "listing": listing})
