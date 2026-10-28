# CampusSwap

**Buy smart, sell easy, waste less.** A student-only Django marketplace for used textbooks and campus essentials.
Group 7: Uday Kumar Reddy Yarradoddi · Sindhu Padmaja Dudekula · Tanu Sree Reddy Gavinnolla

## Quick start

You need Python 3.10+. Bootstrap 5 and Bootstrap Icons are bundled in `static/vendor/`, so the site works **without internet** during the demo.

```bash
# macOS / Linux
./run_demo.sh

# Windows
run_demo.bat
```

Or step by step:

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py fetch_seed_images     # one-time: download real book covers + photos (needs internet)
python manage.py seed_demo --reset     # 12 students, 45 listings, messages, reviews, favourites
python manage.py test                  # 84 automated tests, should end with "OK"
python manage.py runserver             # http://127.0.0.1:8000
```

### Demo accounts

Every account has its own password. **[DEMO_ACCOUNTS.md](DEMO_ACCOUNTS.md)** has the full list and what each account is good for demoing. The main ones are:

| Username | Password | Use it to show |
|---|---|---|
| `priya_s` | `Priya#Swap26` | Main student: 1 unread message, favourites, 5★ seller rating |
| `emily_c` | `Emily#Swap26` | Buyer: shopping for COMP 2052 books |
| `mod_jordan` | `Mod#Swap26` | Moderator (staff with limited permissions) in `/admin/` |
| `admin` | `Admin#Swap26` | Superuser: full admin, 2 open reports waiting |

You can also log in with an email, for example `priya.sharma@student.college.ca`.

### Sample data (real books)

* **32 real textbooks**, matched to the 14 demo courses. Titles and ISBN-13s were checked on Open Library (the tests also check every ISBN check digit), and each listing shows that edition's cover from the Open Library Covers API.
* **13 campus items** (TI-84, Casio fx-991ES, lab coats, desk lamp, office chair and more) with freely licensed photos from Wikimedia Commons.
* All sources and licences are listed on the in-app **/credits/** page.
* `fetch_seed_images` caches the images in `market/seed_images/`, so after one online run the demo works **offline**. Without internet, `seed_demo` draws a simple cover instead, so the site never shows broken images.

## Features

| Area | What it does | Django pieces |
|---|---|---|
| **Guest mode** | Browse, search, Course Finder, item details, seller profiles, recently viewed. Gated actions show a lock and send you to log in, then bring you back (`?next=`). | `member_required` decorator, sessions |
| **Registration** | Sign-up with a student-email check, a unique email/username, password strength rules and meter, and a program choice. Logs you in right away. | `UserCreationForm`, `Profile` (1:1), post_save signal |
| **Login** | Username **or** email, case-insensitive. Password reset by email (prints to the terminal). | Custom auth backend, built-in auth views |
| **Listings** | Create/edit/delete, up to 5 photos (drag & drop with preview), mark sold or relist, condition, category, course and ISBN | `ModelForm`, multi-file `ImageField`, Pillow validation |
| **Search** | Keyword, course code in any format (`comp1030` = `COMP 1030`), ISBN with or without dashes, filters, sort, pagination. The sort is remembered. | `Q` objects, GET forms, `Paginator` |
| **Course Finder** | Program → course → every book for it, cheapest first | `Course` FK, `annotate(Count)` |
| **Messaging** | Per-item conversations, inbox, unread badge in the navbar | `Message` model, context processor |
| **Favourites** | One-tap hearts (AJAX, with a no-JS fallback) | `Favourite` model, `JsonResponse` |
| **Reviews** | 1–5 stars. Only buyers who messaged the seller can review, once per item. The average shows on listings and profiles. | `Review`, `UniqueConstraint`, `CheckConstraint`, `Avg()` |
| **Reports & moderation** | Report button. 3 open reports auto-hide a listing. Admin actions: resolve-and-hide, dismiss-and-restore, suspend users. | `Report`, custom `ModelAdmin` |

## Data model

`Profile` (1:1 User) · `Course` (1:N Listing) · `Listing` (FK seller, FK course) · `Message`, `Review`, `Report` (FK Listing + FK User).
Two supporting tables: `ListingPhoto` (up to 5 photos per listing) and `Favourite` (User ↔ Listing).

## Project layout

```
campusswap_site/   settings, root URLs
accounts/          Profile model, sign-up/login forms, auth backend, profile views   (Tanu)
market/            listings, search, messaging, reviews, reports, admin, seed command (Uday)
templates/         Bootstrap 5 templates, partials, error pages                       (Sindhu)
static/            campusswap.css, campusswap.js, vendored Bootstrap + icons
```

## Configuration

* **Student email rule:** set `CAMPUSSWAP_EMAIL_DOMAINS` (comma-separated), for example `georgebrown.ca`. The default is `.ca,.edu`.
* **Production:** set `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`, then run `collectstatic`.
