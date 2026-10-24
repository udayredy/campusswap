from django.urls import path

from . import views

app_name = "market"

urlpatterns = [
    path("", views.home, name="home"),
    path("guest-vs-member/", views.guest_vs_member, name="guest_vs_member"),
    path("browse/", views.browse, name="browse"),
    path("credits/", views.credits, name="credits"),
    path("courses/", views.course_finder, name="course_finder"),
    path("courses/<int:pk>/", views.course_detail, name="course_detail"),
    path("listings/new/", views.listing_create, name="listing_create"),
    path("listings/<int:pk>/", views.listing_detail, name="listing_detail"),
    path("listings/<int:pk>/edit/", views.listing_edit, name="listing_edit"),
    path("listings/<int:pk>/delete/", views.listing_delete, name="listing_delete"),
    path("listings/<int:pk>/sold/", views.listing_toggle_sold, name="listing_toggle_sold"),
    path("listings/<int:pk>/favourite/", views.favourite_toggle, name="favourite_toggle"),
    path("listings/<int:pk>/review/", views.review_create, name="review_create"),
    path("listings/<int:pk>/report/", views.report_create, name="report_create"),
    path("photos/<int:pk>/delete/", views.photo_delete, name="photo_delete"),
    path("my/listings/", views.my_listings, name="my_listings"),
    path("my/favourites/", views.favourites, name="favourites"),
    path("inbox/", views.inbox, name="inbox"),
    path("inbox/<int:listing_pk>/<int:user_pk>/", views.conversation, name="conversation"),
]
