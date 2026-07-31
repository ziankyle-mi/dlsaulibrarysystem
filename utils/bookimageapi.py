"""
Book Image Fetcher using Open Library API (free, no API key required)
Fetches real book cover images from Open Library database
"""
import os
import threading
import requests
from PIL import Image
from io import BytesIO
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_CACHE_DIR = os.path.join(BASE_DIR, 'database', 'book_covers')
os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)
OPENLIBRARY_SEARCH_URL = 'https://openlibrary.org/search.json'
OPENLIBRARY_COVERS_URL = 'https://covers.openlibrary.org/b'
_session = requests.Session()
_session.headers.update({'User-Agent': 'DLSAU-Library-System/1.0 (book cover fetcher)'})
_memory_cache = {}
_negative_cache = set()
_cache_lock = threading.Lock()
_request_lock = threading.Lock()

def get_cached_image_path(book_code):
    """Returns the cache path for a book's cover image."""
    return os.path.join(IMAGE_CACHE_DIR, f'{book_code}.png')

def _normalize_image(image):
    """Convert to RGB so Tkinter can display every cached/API image reliably."""
    if image.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        if image.mode == 'P':
            image = image.convert('RGBA')
        background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
        return background
    if image.mode != 'RGB':
        return image.convert('RGB')
    return image

def _cache_image(book_code, image):
    normalized = _normalize_image(image)
    with _cache_lock:
        _memory_cache[book_code] = normalized
        _negative_cache.discard(book_code)
    try:
        normalized.save(get_cached_image_path(book_code), 'PNG', optimize=True)
    except Exception as e:
        pass
    return normalized

def _load_disk_cache(book_code):
    cache_path = get_cached_image_path(book_code)
    if not os.path.exists(cache_path):
        return None
    try:
        with Image.open(cache_path) as img:
            return _normalize_image(img.copy())
    except Exception as e:
        pass
        return None

def _get_cached_image(book_code):
    with _cache_lock:
        if book_code in _negative_cache:
            return False
        cached = _memory_cache.get(book_code)
    if cached is not None:
        return cached.copy()
    image = _load_disk_cache(book_code)
    if image is not None:
        with _cache_lock:
            _memory_cache[book_code] = image
        return image.copy()
    return None

def _mark_no_cover(book_code):
    if not book_code:
        return
    with _cache_lock:
        _negative_cache.add(book_code)
        _memory_cache.pop(book_code, None)

def _api_get(url, **kwargs):
    with _request_lock:
        return _session.get(url, **kwargs)

def fetch_book_image(book_title, author_name=None, book_code=None, use_cache=True):
    """
    Fetches book cover image from Open Library API.

    Returns a PIL.Image object or None if not found.
    """
    if book_code and use_cache:
        cached = _get_cached_image(book_code)
        if cached is False:
            return None
        if cached is not None:
            return cached
    try:
        params = {'title': book_title, 'limit': 5, 'fields': 'cover_i,cover_id'}
        if author_name:
            params['author'] = author_name
        response = _api_get(OPENLIBRARY_SEARCH_URL, params=params, timeout=(2, 5))
        response.raise_for_status()
        data = response.json()
        for book in data.get('docs') or []:
            cover_id = book.get('cover_i') or book.get('cover_id')
            if not cover_id:
                continue
            try:
                cover_url = f'{OPENLIBRARY_COVERS_URL}/id/{cover_id}-M.jpg'
                img_response = _api_get(cover_url, timeout=(2, 5))
                if img_response.status_code != 200:
                    continue
                image = _normalize_image(Image.open(BytesIO(img_response.content)))
                if book_code:
                    _cache_image(book_code, image)
                return image.copy()
            except Exception as e:
                pass
                continue
        if book_code:
            _mark_no_cover(book_code)
        pass
        return None
    except requests.exceptions.Timeout:
        pass
        return None
    except requests.exceptions.RequestException as e:
        pass
        return None
    except Exception as e:
        pass
        return None

def load_cover_into_label(label, request_tracker, book_code, book_title, book_author, thumb_size=(150, 200), extra_labels=None):
    """
    Loads a book cover on a background thread and applies it to a Tkinter Label
    on the main thread. Stale requests are ignored when the user selects another book.

    extra_labels: optional list of (label, thumb_size) tuples to update with the same image.
    """
    from PIL import ImageTk
    targets = [(label, thumb_size)]
    if extra_labels:
        targets.extend(extra_labels)
    request_tracker['id'] += 1
    request_id = request_tracker['id']
    request_tracker['book_code'] = book_code
    root = label.winfo_toplevel()
    loading_text = 'Loading...'

    def show_loading():
        if request_tracker['id'] != request_id:
            return
        for idx, (lbl, _) in enumerate(targets):
            try:
                lbl.configure(image='', text='Loading...' if idx == 0 else '')
            except Exception:
                pass
            lbl.image = None
    show_loading()

    def fetch_and_apply():
        if request_tracker['id'] != request_id:
            return
        try:
            image = fetch_book_image(book_title, book_author, book_code, use_cache=True)
            error = None
        except Exception as e:
            pass
            image = None
            error = e
        if request_tracker['id'] != request_id:
            return

        def apply_result():
            if request_tracker['id'] != request_id:
                return
            if error:
                for idx, (lbl, _) in enumerate(targets):
                    try:
                        lbl.configure(image='', text='Error' if idx == 0 else '')
                    except Exception:
                        pass
                    lbl.image = None
                return
            if image:
                for lbl, size in targets:
                    display = image.copy()
                    display.thumbnail(size, Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(display)
                    try:
                        lbl.configure(image=photo, text='')
                    except Exception:
                        pass
                    lbl.image = photo
            else:
                for idx, (lbl, _) in enumerate(targets):
                    try:
                        lbl.configure(image='', text='No cover' if idx == 0 else '')
                    except Exception:
                        pass
                    lbl.image = None
        root.after(0, apply_result)
    threading.Thread(target=fetch_and_apply, daemon=True, name=f'cover-{book_code}').start()

def fetch_book_info(book_title, author_name=None):
    """Fetches detailed book information from Open Library."""
    try:
        params = {'title': book_title, 'limit': 1, 'fields': 'title,author_name,isbn,first_publish_year,publisher,cover_i,cover_id'}
        if author_name:
            params['author'] = author_name
        response = _api_get(OPENLIBRARY_SEARCH_URL, params=params, timeout=(2, 5))
        response.raise_for_status()
        data = response.json()
        if data.get('docs'):
            book = data['docs'][0]
            cover_id = book.get('cover_i') or book.get('cover_id')
            return {'title': book.get('title', ''), 'author': book.get('author_name', ['Unknown'])[0] if book.get('author_name') else 'Unknown', 'isbn': book.get('isbn', ['N/A'])[0] if book.get('isbn') else 'N/A', 'first_publish_year': book.get('first_publish_year', 'Unknown'), 'publisher': book.get('publisher', ['Unknown'])[0] if book.get('publisher') else 'Unknown', 'has_cover': bool(cover_id), 'cover_id': cover_id}
        return None
    except Exception as e:
        pass
        return None

def clear_image_cache():
    """Clears all cached book images from disk and memory."""
    with _cache_lock:
        _memory_cache.clear()
        _negative_cache.clear()
    try:
        for filename in os.listdir(IMAGE_CACHE_DIR):
            file_path = os.path.join(IMAGE_CACHE_DIR, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
        pass
    except Exception as e:
        pass