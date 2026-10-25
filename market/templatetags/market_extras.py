from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """Rebuild the current querystring with some keys changed (used by pagination & filter chips)."""
    query = context["request"].GET.copy()
    for k, v in kwargs.items():
        if v in (None, ""):
            query.pop(k, None)
        else:
            query[k] = v
    return query.urlencode()


@register.inclusion_tag("market/_stars.html")
def stars(value, size=""):
    value = value or 0
    full = int(value)
    half = 1 if value - full >= 0.5 else 0
    return {"full": range(full), "half": half, "empty": range(5 - full - half), "size": size}


@register.filter
def money(value):
    if value is None:
        return ""
    if value == 0:
        return "Free"
    return f"${value:,.0f}" if value == int(value) else f"${value:,.2f}"


@register.filter
def bs(bound_field, extra=""):
    """Render a form widget with the right Bootstrap class (+ is-invalid when it has errors)."""
    widget = bound_field.field.widget
    name = widget.__class__.__name__
    if name in ("Select", "SelectMultiple"):
        css = "form-select"
    elif name in ("CheckboxInput",):
        css = "form-check-input"
    elif name in ("RadioSelect", "CheckboxSelectMultiple"):
        css = ""
    else:
        css = "form-control"
    if bound_field.errors:
        css += " is-invalid"
    if extra:
        css += " " + extra
    attrs = {"class": css.strip()} if css.strip() else {}
    if bound_field.errors:
        attrs["aria-invalid"] = "true"
    if bound_field.help_text:
        attrs["aria-describedby"] = f"{bound_field.auto_id}_help"
    return bound_field.as_widget(attrs=attrs)



@register.filter
def ago(value):
    """'3 days, 4 hours' -> '3 days ago'; under a minute -> 'just now'."""
    from django.utils.timesince import timesince

    if not value:
        return ""
    first = timesince(value).split(",")[0].replace("\xa0", " ")
    return "just now" if first.startswith("0 ") else f"{first} ago"
