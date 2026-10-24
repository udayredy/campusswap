from .models import Listing, Message


def navbar(request):
    data = {"nav_categories": Listing.Category.choices}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        data["unread_count"] = Message.objects.filter(recipient=user, is_read=False).count()
        data["fav_count"] = user.favourites.count()
    return data
