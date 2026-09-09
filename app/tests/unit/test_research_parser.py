from __future__ import annotations

from app.research.parser import parse_html
from app.research.signals import build_signals

_HTML = """
<html lang="en"><head>
<title>ABC Dental Clinic - Dhaka</title>
<meta name="description" content="Family dentistry in Dhaka">
<meta name="viewport" content="width=device-width">
</head><body>
<nav><a href="/services">Services</a><a href="/contact">Contact</a><a href="/faq">FAQ</a></nav>
<h1>Welcome to ABC Dental</h1>
<h2>Our Services</h2>
<a href="https://facebook.com/abcdental">Facebook</a>
<a href="tel:+8801712345678">Call us</a>
<a href="https://wa.me/8801712345678">WhatsApp</a>
<p>Contact us at info@abcdental.com for an appointment.</p>
<script src="/wp-content/themes/x.js"></script>
</body></html>
"""


def test_parse_html_extracts_structure():
    p = parse_html(_HTML, "https://abcdental.com/")
    assert p.title == "ABC Dental Clinic - Dhaka"
    assert p.meta_description == "Family dentistry in Dhaka"
    assert p.has_viewport_meta is True
    assert "info@abcdental.com" in p.emails
    assert "+8801712345678" in p.phones
    assert p.social_profiles["facebook"].startswith("https://facebook.com")
    assert p.social_profiles["whatsapp"].startswith("https://wa.me")
    assert "wordpress" in p.tech_signals
    assert "faq" in " ".join(p.nav_labels).lower()


def test_signals_are_conservative():
    p = parse_html(_HTML, "https://abcdental.com/")
    from app.db.models.enums import WebsiteStatus
    from app.research.http_client import FetchResult

    fr = FetchResult(requested_url="https://abcdental.com/", final_url="https://abcdental.com/",
                     status=WebsiteStatus.ACTIVE, html=_HTML)
    sig = build_signals(
        prospect={"website": "https://abcdental.com", "rating": 4.6, "review_count": 88},
        fetch=fr, pages=[p],
    )
    assert sig.website.has_booking_mechanism is False  # no booking link/keyword
    assert sig.website.is_https is True
    assert sig.website.social_profiles.get("facebook")
    assert sig.business.rating == 4.6


def test_no_website_signals():
    sig = build_signals(prospect={"business_name": "X", "rating": None}, fetch=None, pages=[])
    assert sig.website.exists is False
    assert sig.website.pages_analyzed == 0
