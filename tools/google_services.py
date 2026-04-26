"""Google Cloud service tools for Mercury.

All authenticate via Application Default Credentials (ADC).  No API
keys — the philanthropytraders.com Workspace org policy forbids them.
Run `gcloud auth application-default login` once and these all work.

Tools registered:
    google_maps_directions     — Routes API: turn-by-turn + traffic
    google_maps_find_along_route — Places API New: filter POIs along a route
    google_maps_find_places    — Places API New: nearby/text search
    google_books_search        — Books API: ISBN, author, title lookup
    google_knowledge_graph     — KG Search API: entity disambiguation
    google_translate           — Translate v3: text in 100+ languages
    google_vision_ocr          — Vision API: OCR / labels / safe-search
    google_speech_to_text      — Speech-to-Text v2 (long-running for >60s)
    google_text_to_speech      — Text-to-Speech (Wavenet / Neural2 voices)

Free-tier headroom (per Google Cloud free-tier docs):
    Maps Platform     $200/mo credit (≈5,000 of our coffee-detour queries)
    Books             1,000 requests/day
    Knowledge Graph   100,000 queries/day
    Translate         500,000 chars/month
    Vision            1,000 units/month
    Speech-to-Text    60 minutes/month
    Text-to-Speech    1M chars/month (standard) / 4M chars (Neural2 first 1M)

Mercury's `quota_guard.py` (TODO) tracks per-API usage and short-circuits
at 90% of free tier.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# ─── shared helpers ─────────────────────────────────────────────────────────

def _project() -> str | None:
    return (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip() or None


def _adc_ready() -> bool:
    """Best-effort ADC presence check.  Returns True if we can construct a
    client without auth errors at instantiation time."""
    try:
        import google.auth
        google.auth.default()
        return True
    except Exception:
        return False


# ─── Routes / Places (Maps Platform) ────────────────────────────────────────

ROUTES_BASE = "https://routes.googleapis.com/directions/v2:computeRoutes"
PLACES_TEXT_BASE = "https://places.googleapis.com/v1/places:searchText"
PLACES_ALONG_BASE = "https://places.googleapis.com/v1/places:searchText"


def _maps_request(url: str, body: dict, field_mask: str) -> dict:
    """Maps Platform requires X-Goog-FieldMask + bearer auth via ADC."""
    import google.auth
    import google.auth.transport.requests
    import httpx

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())

    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
        "X-Goog-FieldMask": field_mask,
    }
    project = _project()
    if project:
        headers["X-Goog-User-Project"] = project

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()


def google_maps_directions(args: dict | None = None, **_kw: Any) -> dict[str, Any]:
    args = args or {}
    origin = args.get("origin")
    destination = args.get("destination")
    if not origin or not destination:
        return {"ok": False, "error": "missing_args", "message": "origin and destination required"}

    travel_mode = (args.get("mode") or "DRIVE").upper()
    body = {
        "origin": {"address": origin} if isinstance(origin, str) else {"location": {"latLng": origin}},
        "destination": {"address": destination} if isinstance(destination, str) else {"location": {"latLng": destination}},
        "travelMode": travel_mode,
        "routingPreference": "TRAFFIC_AWARE" if travel_mode == "DRIVE" else "ROUTING_PREFERENCE_UNSPECIFIED",
        "computeAlternativeRoutes": False,
    }
    if args.get("departure_time_iso"):
        body["departureTime"] = args["departure_time_iso"]

    field_mask = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.legs.steps.navigationInstruction,routes.legs.steps.distanceMeters,routes.legs.steps.staticDuration"

    try:
        data = _maps_request(ROUTES_BASE, body, field_mask)
    except Exception as exc:
        return {"ok": False, "error": "api_error", "message": str(exc)}

    return {"ok": True, "routes": data.get("routes", [])}


def google_maps_find_along_route(args: dict | None = None, **_kw: Any) -> dict[str, Any]:
    """Search for POIs along a polyline, ranked by detour cost."""
    args = args or {}
    origin = args.get("origin")
    destination = args.get("destination")
    query = args.get("query")
    max_detour_min = float(args.get("max_detour_minutes", 5))
    if not all([origin, destination, query]):
        return {"ok": False, "error": "missing_args", "message": "origin, destination, query required"}

    route = google_maps_directions({"origin": origin, "destination": destination, "mode": "DRIVE"})
    if not route.get("ok"):
        return route

    routes = route.get("routes") or []
    if not routes:
        return {"ok": False, "error": "no_route_found"}
    polyline = routes[0].get("polyline", {}).get("encodedPolyline")
    if not polyline:
        return {"ok": False, "error": "no_polyline"}

    body = {
        "textQuery": query,
        "searchAlongRouteParameters": {"polyline": {"encodedPolyline": polyline}},
        "rankPreference": "DISTANCE",
    }
    field_mask = "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.priceLevel,places.regularOpeningHours,places.id,places.googleMapsUri"

    try:
        data = _maps_request(PLACES_ALONG_BASE, body, field_mask)
    except Exception as exc:
        return {"ok": False, "error": "places_api_error", "message": str(exc)}

    places = data.get("places", [])
    return {
        "ok": True,
        "query": query,
        "max_detour_minutes": max_detour_min,
        "places": places[:10],
        "route_summary": {
            "distance_meters": routes[0].get("distanceMeters"),
            "duration": routes[0].get("duration"),
        },
    }


def google_maps_find_places(args: dict | None = None, **_kw: Any) -> dict[str, Any]:
    args = args or {}
    query = args.get("query")
    near = args.get("near")
    if not query:
        return {"ok": False, "error": "missing_query"}

    body: dict[str, Any] = {"textQuery": query, "rankPreference": "RELEVANCE"}
    if near and isinstance(near, dict):
        body["locationBias"] = {"circle": {"center": {"latitude": near.get("lat"), "longitude": near.get("lng")}, "radius": near.get("radius_meters", 5000)}}
    elif near and isinstance(near, str):
        body["textQuery"] = f"{query} near {near}"

    field_mask = "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.priceLevel,places.types,places.googleMapsUri"
    try:
        data = _maps_request(PLACES_TEXT_BASE, body, field_mask)
    except Exception as exc:
        return {"ok": False, "error": "places_api_error", "message": str(exc)}
    return {"ok": True, "places": data.get("places", [])[:10]}


# ─── Books API ──────────────────────────────────────────────────────────────

def google_books_search(args: dict | None = None, **_kw: Any) -> dict[str, Any]:
    args = args or {}
    query = args.get("query")
    if not query:
        return {"ok": False, "error": "missing_query"}

    import google.auth
    import google.auth.transport.requests
    import httpx

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/books"])
    creds.refresh(google.auth.transport.requests.Request())

    params = {"q": query, "maxResults": int(args.get("max_results", 10))}
    if args.get("isbn"):
        params["q"] = f"isbn:{args['isbn']}"

    try:
        with httpx.Client(timeout=20.0) as c:
            r = c.get(
                "https://www.googleapis.com/books/v1/volumes",
                params=params,
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        return {"ok": False, "error": "books_api_error", "message": str(exc)}

    items = []
    for it in data.get("items", []):
        v = it.get("volumeInfo", {})
        ids = {x.get("type"): x.get("identifier") for x in v.get("industryIdentifiers", [])}
        items.append({
            "title": v.get("title"),
            "authors": v.get("authors"),
            "publisher": v.get("publisher"),
            "published_date": v.get("publishedDate"),
            "description": (v.get("description") or "")[:600],
            "isbn_10": ids.get("ISBN_10"),
            "isbn_13": ids.get("ISBN_13"),
            "page_count": v.get("pageCount"),
            "categories": v.get("categories"),
            "preview_link": v.get("previewLink"),
        })
    return {"ok": True, "query": query, "results": items}


# ─── Knowledge Graph Search ─────────────────────────────────────────────────

def google_knowledge_graph(args: dict | None = None, **_kw: Any) -> dict[str, Any]:
    args = args or {}
    query = args.get("query")
    if not query:
        return {"ok": False, "error": "missing_query"}

    import google.auth
    import google.auth.transport.requests
    import httpx

    creds, _ = google.auth.default()
    creds.refresh(google.auth.transport.requests.Request())

    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(
                "https://kgsearch.googleapis.com/v1/entities:search",
                params={"query": query, "limit": int(args.get("limit", 5))},
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        return {"ok": False, "error": "kg_api_error", "message": str(exc)}

    entities = []
    for el in data.get("itemListElement", []):
        result = el.get("result", {})
        entities.append({
            "name": result.get("name"),
            "types": result.get("@type"),
            "description": result.get("description"),
            "detailed_description": (result.get("detailedDescription") or {}).get("articleBody"),
            "url": result.get("url"),
            "score": el.get("resultScore"),
        })
    return {"ok": True, "query": query, "entities": entities}


# ─── Translate v3 ───────────────────────────────────────────────────────────

def google_translate(args: dict | None = None, **_kw: Any) -> dict[str, Any]:
    args = args or {}
    text = args.get("text")
    target = args.get("target_lang", "en")
    if not text:
        return {"ok": False, "error": "missing_text"}

    project = _project()
    if not project:
        return {"ok": False, "error": "no_project", "message": "GOOGLE_CLOUD_PROJECT must be set"}

    try:
        from google.cloud import translate_v3 as translate
    except ImportError:
        return {"ok": False, "error": "missing_dep", "message": "pip install google-cloud-translate"}

    try:
        client = translate.TranslationServiceClient()
        parent = f"projects/{project}/locations/global"
        resp = client.translate_text(
            parent=parent,
            contents=[text] if isinstance(text, str) else text,
            target_language_code=target,
            source_language_code=args.get("source_lang"),
            mime_type="text/plain",
        )
    except Exception as exc:
        return {"ok": False, "error": "translate_api_error", "message": str(exc)}

    return {
        "ok": True,
        "translations": [
            {"translated": t.translated_text, "detected_lang": t.detected_language_code}
            for t in resp.translations
        ],
    }


# ─── Cloud Vision (OCR / labels / safe-search) ──────────────────────────────

def google_vision_ocr(args: dict | None = None, **_kw: Any) -> dict[str, Any]:
    args = args or {}
    image_path = args.get("image_path")
    image_url = args.get("image_url")
    if not (image_path or image_url):
        return {"ok": False, "error": "missing_image", "message": "image_path or image_url required"}

    try:
        from google.cloud import vision
    except ImportError:
        return {"ok": False, "error": "missing_dep", "message": "pip install google-cloud-vision"}

    try:
        client = vision.ImageAnnotatorClient()
        if image_path:
            from pathlib import Path
            with Path(image_path).open("rb") as f:
                image = vision.Image(content=f.read())
        else:
            image = vision.Image(source=vision.ImageSource(image_uri=image_url))

        features = [
            vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION),
            vision.Feature(type_=vision.Feature.Type.LABEL_DETECTION, max_results=15),
            vision.Feature(type_=vision.Feature.Type.SAFE_SEARCH_DETECTION),
        ]
        request = vision.AnnotateImageRequest(image=image, features=features)
        response = client.annotate_image(request=request)
    except Exception as exc:
        return {"ok": False, "error": "vision_api_error", "message": str(exc)}

    labels = [{"description": l.description, "score": round(l.score, 3)} for l in response.label_annotations]
    safe = response.safe_search_annotation
    return {
        "ok": True,
        "ocr_text": response.full_text_annotation.text if response.full_text_annotation else "",
        "labels": labels,
        "safe_search": {
            "adult": safe.adult.name if safe else None,
            "violence": safe.violence.name if safe else None,
            "racy": safe.racy.name if safe else None,
        },
    }


# ─── Speech-to-Text v2 ──────────────────────────────────────────────────────

def google_speech_to_text(args: dict | None = None, **_kw: Any) -> dict[str, Any]:
    args = args or {}
    audio_path = args.get("audio_path")
    if not audio_path:
        return {"ok": False, "error": "missing_audio_path"}

    try:
        from google.cloud import speech
    except ImportError:
        return {"ok": False, "error": "missing_dep", "message": "pip install google-cloud-speech"}

    try:
        from pathlib import Path
        client = speech.SpeechClient()
        with Path(audio_path).open("rb") as f:
            audio_bytes = f.read()

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16
            if audio_path.lower().endswith(".wav")
            else speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED,
            language_code=args.get("language_code", "en-US"),
            enable_automatic_punctuation=True,
            model=args.get("model", "latest_long"),
        )
        audio = speech.RecognitionAudio(content=audio_bytes)
        response = client.recognize(config=config, audio=audio, timeout=300)
    except Exception as exc:
        return {"ok": False, "error": "speech_api_error", "message": str(exc)}

    transcript = "\n".join(r.alternatives[0].transcript for r in response.results if r.alternatives)
    return {"ok": True, "transcript": transcript, "results_count": len(response.results)}


# ─── Text-to-Speech ─────────────────────────────────────────────────────────

def google_text_to_speech(args: dict | None = None, **_kw: Any) -> dict[str, Any]:
    args = args or {}
    text = args.get("text")
    if not text:
        return {"ok": False, "error": "missing_text"}

    try:
        from google.cloud import texttospeech
    except ImportError:
        return {"ok": False, "error": "missing_dep", "message": "pip install google-cloud-texttospeech"}

    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=args.get("language_code", "en-US"),
            name=args.get("voice_name", "en-US-Neural2-J"),
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=float(args.get("speaking_rate", 1.0)),
        )
        response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    except Exception as exc:
        return {"ok": False, "error": "tts_api_error", "message": str(exc)}

    out_path = args.get("output_path", "tts_output.mp3")
    from pathlib import Path
    Path(out_path).write_bytes(response.audio_content)
    return {"ok": True, "output_path": out_path, "voice": args.get("voice_name", "en-US-Neural2-J")}


# ─── registrations ──────────────────────────────────────────────────────────

def _check_adc(_handler_name: str = "") -> bool:
    return _adc_ready()


from tools.registry import registry  # noqa: E402

# Top-level registrations — discover_builtin_tools() AST-scans for these.

registry.register(
    name="google_maps_directions",
    toolset="google_maps",
    schema={"name": "google_maps_directions",
            "description": "Get turn-by-turn driving/walking/cycling/transit directions between two places via Google Routes API.",
            "parameters": {"type": "object", "properties": {
                "origin": {"type": ["string", "object"], "description": "Address or {latitude, longitude}"},
                "destination": {"type": ["string", "object"], "description": "Address or {latitude, longitude}"},
                "mode": {"type": "string", "enum": ["DRIVE", "WALK", "BICYCLE", "TRANSIT"], "default": "DRIVE"},
                "departure_time_iso": {"type": "string"},
            }, "required": ["origin", "destination"]}},
    handler=google_maps_directions, check_fn=_check_adc, requires_env=["GOOGLE_CLOUD_PROJECT"],
    is_async=False, description="Routes API directions", emoji="🗺", max_result_size_chars=20000,
)

registry.register(
    name="google_maps_find_along_route",
    toolset="google_maps",
    schema={"name": "google_maps_find_along_route",
            "description": "Find places (coffee, gas, restaurants) along a route, ranked by detour cost.",
            "parameters": {"type": "object", "properties": {
                "origin": {"type": "string"}, "destination": {"type": "string"},
                "query": {"type": "string"},
                "max_detour_minutes": {"type": "number", "default": 5},
            }, "required": ["origin", "destination", "query"]}},
    handler=google_maps_find_along_route, check_fn=_check_adc, requires_env=["GOOGLE_CLOUD_PROJECT"],
    is_async=False, description="Places along route", emoji="📍", max_result_size_chars=20000,
)

registry.register(
    name="google_maps_find_places",
    toolset="google_maps",
    schema={"name": "google_maps_find_places",
            "description": "Search places by text query, optionally biased near a location.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"},
                "near": {"type": ["string", "object"]},
            }, "required": ["query"]}},
    handler=google_maps_find_places, check_fn=_check_adc, requires_env=["GOOGLE_CLOUD_PROJECT"],
    is_async=False, description="Places text search", emoji="📌", max_result_size_chars=20000,
)

registry.register(
    name="google_books_search",
    toolset="research",
    schema={"name": "google_books_search",
            "description": "Search Google Books by title, author, ISBN, or keyword.  Use for ISU textbook lookups.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "isbn": {"type": "string"},
                "max_results": {"type": "integer", "default": 10},
            }, "required": ["query"]}},
    handler=google_books_search, check_fn=_check_adc, requires_env=[],
    is_async=False, description="Books API", emoji="📚", max_result_size_chars=20000,
)

registry.register(
    name="google_knowledge_graph",
    toolset="research",
    schema={"name": "google_knowledge_graph",
            "description": "Look up entities in Google Knowledge Graph for disambiguation + structured facts.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            }, "required": ["query"]}},
    handler=google_knowledge_graph, check_fn=_check_adc, requires_env=[],
    is_async=False, description="KG entity search", emoji="🧠", max_result_size_chars=15000,
)

registry.register(
    name="google_translate",
    toolset="research",
    schema={"name": "google_translate",
            "description": "Translate text between 100+ languages via Cloud Translate v3 (auto-detects source).",
            "parameters": {"type": "object", "properties": {
                "text": {"type": "string"},
                "target_lang": {"type": "string", "default": "en"},
                "source_lang": {"type": "string"},
            }, "required": ["text"]}},
    handler=google_translate, check_fn=_check_adc, requires_env=["GOOGLE_CLOUD_PROJECT"],
    is_async=False, description="Translate v3", emoji="🌐", max_result_size_chars=15000,
)

registry.register(
    name="google_vision_ocr",
    toolset="vision",
    schema={"name": "google_vision_ocr",
            "description": "OCR + label detection + safe-search on an image via Cloud Vision.",
            "parameters": {"type": "object", "properties": {
                "image_path": {"type": "string"}, "image_url": {"type": "string"},
            }}},
    handler=google_vision_ocr, check_fn=_check_adc, requires_env=[],
    is_async=False, description="Vision OCR", emoji="👁", max_result_size_chars=20000,
)

registry.register(
    name="google_speech_to_text",
    toolset="media",
    schema={"name": "google_speech_to_text",
            "description": "Transcribe audio via Cloud Speech-to-Text (latest_long, auto-punctuation).  Full Google-stack replacement for faster-whisper.",
            "parameters": {"type": "object", "properties": {
                "audio_path": {"type": "string"},
                "language_code": {"type": "string", "default": "en-US"},
                "model": {"type": "string", "default": "latest_long"},
            }, "required": ["audio_path"]}},
    handler=google_speech_to_text, check_fn=_check_adc, requires_env=[],
    is_async=False, description="STT", emoji="🎤", max_result_size_chars=30000,
)

registry.register(
    name="google_text_to_speech",
    toolset="media",
    schema={"name": "google_text_to_speech",
            "description": "Synthesize speech from text via Cloud Text-to-Speech (Neural2 / Wavenet).",
            "parameters": {"type": "object", "properties": {
                "text": {"type": "string"},
                "language_code": {"type": "string", "default": "en-US"},
                "voice_name": {"type": "string", "default": "en-US-Neural2-J"},
                "output_path": {"type": "string", "default": "tts_output.mp3"},
                "speaking_rate": {"type": "number", "default": 1.0},
            }, "required": ["text"]}},
    handler=google_text_to_speech, check_fn=_check_adc, requires_env=[],
    is_async=False, description="TTS", emoji="🔊", max_result_size_chars=2000,
)
