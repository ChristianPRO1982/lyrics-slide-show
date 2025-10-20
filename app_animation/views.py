from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import translation
from PIL import Image
import qrcode
import io, base64
from .SQL_animation import Animation, BackgroundImageSubmission, BackgroundImage
from .utils import all_lyrics
from app_song.SQL_song import Song
from app_group.SQL_group import Group
from app_main.utils import is_no_loader, is_moderator, get_song_params, list_fonts, font_class_by_name, site_messages
from app_main.SQL_main import Site

# for upload image
import secrets
from pathlib import Path
from typing import Optional
from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from app_main.params import get_image_params
from . import utils
import shutil


def animations(request):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        if group != 0:
            group_selected = group.name
    
    if group_selected:
        if request.method == 'POST':

            if request.method == 'POST':
                new_animation = Animation(
                                group_id = group_id,
                                name = request.POST.get('txt_new_name'),
                                description = request.POST.get('txt_new_description'),
                                date = request.POST.get('dt_new_date'),
                            )
                new_animation.save()
                request.POST = request.POST.copy()
                request.POST['txt_new_name'] = ''
                request.POST['txt_new_description'] = ''
                request.POST['txt_new_date'] = ''
                
        animations = Animation.get_all_animations(group_id)
    
    else:
        animations = []
        error = "[ERR1]"

    if is_moderator(request): ismoderator = "moderator"
    else: ismoderator = None


    return render(request, 'app_animation/animations.html', {
        'animations': animations,
        'name': request.POST.get('txt_new_name', ''),
        'description': request.POST.get('txt_new_description', ''),
        'date': request.POST.get('txt_new_date', ''),
        'group_selected': group_selected,
        'error': error,
        'l_site_messages': site_messages(request, moderator=True),
        'css': css,
        'no_loader': no_loader,
        'ismoderator': ismoderator,
        'pending_submissions_count': BackgroundImageSubmission.pending_submissions_count(),
        })


def modify_animation(request, animation_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    animation = None
    songs_already_in = []
    list_lyrics = []
    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        group_selected = group.name
    
    if group_selected:
        animation = Animation.get_animation_by_id(animation_id, group_id)
        if not animation:
            return redirect('animations')

        if request.method == 'POST':
            if 'btn_cancel' not in request.POST:
                if not animation.name:
                    error = "[ERR2]"
                else:
                    animation.name = request.POST.get('txt_name')
                    animation.description = request.POST.get('txt_description')
                    animation.date = request.POST.get('dt_date')
                    animation.padding = int(request.POST.get('sel_padding', 50))
                    animation.font_size = request.POST.get('sel_font_size', 60)
                    animation.font = request.POST.get('sel_font', 'Arial')
                    change_colors = request.POST.get('rad_animation_colors', 'no_change').split('|')
                    image_scout = request.POST.get('box_image_scout', 'off')
                    image_scout_inversee = request.POST.get('box_image_scout_inversee', 'off')
                    if len(change_colors) == 2:
                        animation.color_rgba = change_colors[0]
                        animation.bg_rgba = change_colors[1]
                    if image_scout == 'on':
                        animation.bg_rgba = "image_scout"
                    if image_scout_inversee == 'on':
                        animation.bg_rgba = "image_scout_inversee"
                    animation.save()

                    if request.POST.get('txt_new_songs', '').strip():
                        new_songs = request.POST.get('txt_new_songs').split('|')
                        for song_id in new_songs:
                            animation.new_song_verses(song_id)
                    
                    for song in animation.songs:
                        if request.POST.get(f'box_delete_song_{song['animation_song_id']}', 'off') == 'on':
                            animation.delete_song(song['animation_song_id'])
                        else:
                            animation.update_animation_song(
                                song['animation_song_id'],
                                request.POST.get(f'lis_move_to_{song['animation_song_id']}'),
                                request.POST.get(f'sel_font_{song['animation_song_id']}'),
                                request.POST.get(f'sel_font_size_{song['animation_song_id']}'),
                                request.POST.get(f'rad_song_colors_{song['animation_song_id']}',  'no_change').split('|'),
                                )
                    
                    # update verses
                    for verse in animation.verses:
                        animation_song_id = verse['animation_song_id']
                        verse_id = verse['verse_id']
                        box_name = f"box_verse_{animation_song_id}_{verse_id}"
                        
                        if request.POST.get(box_name, 'off') == 'on':
                            selected = True
                        else:
                            selected = False
                        if not animation.update_animation_verse(
                            animation_song_id,
                            verse_id,
                            selected,
                            request.POST.get(f"sel_verse_font_{animation_song_id}_{verse_id}"),
                            request.POST.get(f"sel_verse_font_size_{animation_song_id}_{verse_id}"),
                            request.POST.get(f"rad_verse_colors_{animation_song_id}_{verse_id}", 'no_change').split('|'),
                            ):
                            error = "[ERR31]"
                
                # reload animation
                animation.new_song_verses_all()
                animation = Animation.get_animation_by_id(animation_id, group_id)

            if any(key in request.POST for key in ['btn_save_exit', 'btn_cancel']):
                return redirect('lyrics_slide_show', animation_id=animation_id)
        
            # Recalculate the 'order' for all songs
            for index, song in enumerate(animation.songs):
                animation.update_song_num(song['animation_song_id'], (index + 1) * 2)
            animation.all_songs()

        # import song's lyrics
        database = ''
        list_lyrics = []
        for song in animation.songs:
            song_lyrics = Song.get_song_by_id(song['song_id'], request.user.is_authenticated)
            song_params = get_song_params(request)
            song_lyrics.verse_max_lines = song_params['verse_max_lines']
            song_lyrics.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
            song_lyrics.get_verses()
            
            full_title = song_lyrics.full_title
            list_lyrics.append({
                'song_id': song['song_id'],
                'full_title': song_lyrics.full_title,
                'lyrics':  song_lyrics.get_lyrics(),
            })
        
        songs_already_in = animation.get_songs_already_in()

        font_sizes = range(30, 101, 5)
        font_sizes_decreasing = range(-20, 0, 5)
        font_sizes_increasing = range(5, 21, 5)

    return render(request, 'app_animation/modify_animation.html', {
        'animation': animation,
        'all_songs': Song.get_all_songs(request.user.is_authenticated),
        'songs_already_in': songs_already_in,
        'list_lyrics': list_lyrics,
        'group_selected': group_selected,
        'font_sizes': font_sizes,
        'font_sizes_decreasing': font_sizes_decreasing,
        'font_sizes_increasing': font_sizes_increasing,
        'list_fonts': list_fonts(),
        'list_padding': range(10, 121, 5),
        'animation_font_class': font_class_by_name(animation.font),
        'error': error,
        'l_site_messages': site_messages(request),
        'css': css,
        'no_loader': no_loader,
    })


def delete_animation(request, animation_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    animation = None
    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        group_selected = group.name
    
    if group_selected:
        animation = Animation.get_animation_by_id(animation_id, group_id)
        if not animation:
            return redirect('animations')

        if request.method == 'POST':
            if 'btn_delete' in request.POST:
                animation.delete()
            return redirect('animations')

    return render(request, 'app_animation/delete_animation.html', {
        'animation': animation,
        'group_selected': group_selected,
        'error': error,
        'l_site_messages': site_messages(request),
        'css': css,
        'no_loader': no_loader,
    })


def lyrics_slide_show(request, animation_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    animation = None
    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        group_selected = group.name
    
    if group_selected:
        animation = Animation.get_animation_by_id(animation_id, group_id)
        if not animation:
            return redirect('animations')
        
    slides = animation.get_slides()
    slides = all_lyrics(slides)
    slides_sliced = []
    preview_animation_song_id = -1
    for slide in slides:
        max_length = 100
        if len(slide['text']) > max_length:
            text = slide['text'][:max_length]
            ext = " <i>[...]</i>"
        else:
            text = slide['text']
            ext = ''

        # Remove unwanted HTML tags at the end of text
        for suffix in ['<br', '<b', '<']:
            if text.endswith(suffix):
                text = text[:-len(suffix)]

        if preview_animation_song_id != slide['animation_song_id']:
            current_slide = -1
        preview_animation_song_id = slide['animation_song_id']
        current_slide += 1

        slides_sliced.append({
            'animation_song_id': slide['animation_song_id'],
            'verse_id': slide['verse_id'],
            'full_title': slide['full_title'],
            'chorus': slide['chorus'],
            'num_verse': slide['num_verse'],
            'followed': slide['followed'],
            'text': text + ext,
            'new_animation_song': slide['new_animation_song'],
            'current_slide': current_slide,
        })
    if not slides:
        if animation.count_verses() == 0:
            error = "[ERR30]"
        else:
            error = "[ERR17]"

    # QR-CODE
    img_qr_code = ''
    try:
        link_to_copy = f'https://www.carthographie.fr/animations/lyrics_slide_show/all_lyrics/{animation_id}/'

        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(link_to_copy)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_qr_code = base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        error = "[ERR35]"

    return render(request, 'app_animation/lyrics_slide_show.html', {
        'animation': animation,
        'group_selected': group_selected,
        'slides': slides,
        'slides_sliced': slides_sliced,
        'link_to_copy': link_to_copy,
        'img_qr_code': img_qr_code,
        'error': error,
        'l_site_messages': site_messages(request),
        'css': css,
        'no_loader': no_loader,
    })


def modify_colors(request, xxx_id=None):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    if "modify_colors_animation" in request.resolver_match.url_name:
        target = 'animation'
        animation_id = xxx_id
    elif "modify_colors_song" in request.resolver_match.url_name:
        target = 'song'
        animation_id = Animation.get_animation_id_by_song_id(xxx_id)
    elif "modify_colors_verse" in request.resolver_match.url_name:
        target = 'verse'
        verse_id = int(request.GET.get('verse_id', 0))
        animation_id = Animation.get_animation_id_by_verse_id(xxx_id, verse_id)

    animation = None
    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        group_selected = group.name
    
    if group_selected:
        animation = Animation.get_animation_by_id(animation_id, group_id)
        if not animation:
            return redirect('animations')

        if request.method == 'POST':
            if 'btn_del_song_colors' in request.POST:
                animation.update_animation_song_colors(xxx_id, None, None)
            elif 'btn_del_verse_colors' in request.POST:
                animation.update_animation_verse_colors(xxx_id, verse_id, None, None)
            elif 'btn_save' in request.POST:
                if target == 'animation':
                    animation.color_rgba = request.POST.get('text_color')
                    animation.bg_rgba = request.POST.get('bg_color')
                    animation.save()
                elif target == 'song':
                    animation.update_animation_song_colors(xxx_id, request.POST.get('text_color'), request.POST.get('bg_color'))
                elif target == 'verse':
                    animation.update_animation_verse_colors(xxx_id,
                                                            verse_id,
                                                            request.POST.get('text_color'),
                                                            request.POST.get('bg_color'))
            animation = Animation.get_animation_by_id(animation_id, group_id)
            return redirect('modify_animation', animation_id=animation_id)
    
    song_full_title = ''
    verse_preview = ''
    if target == 'animation':
        color_rgba = animation.color_rgba
        bg_rbga = animation.bg_rgba
    elif target == 'song':
        for song in animation.songs:
            if song['animation_song_id'] == xxx_id:
                song_full_title = song['full_title']
                color_rgba = song['color_rgba']
                bg_rbga = song['bg_rgba']
                break
    elif target == 'verse':
        for song in animation.songs:
            if song['animation_song_id'] == xxx_id:
                song_full_title = song['full_title']
                break
        for verse in animation.verses:
            if verse['animation_song_id'] == xxx_id and verse['verse_id'] == verse_id:
                color_rgba = verse['color_rgba']
                bg_rbga = verse['bg_rgba']
                verse_preview = verse['text']
                break

    return render(request, 'app_animation/modify_colors.html', {
        'animation': animation,
        'target': target,
        'song_full_title': song_full_title,
        'verse_preview': verse_preview,
        'color_rgba': color_rgba,
        'bg_rgba': bg_rbga,
        'group_selected': group_selected,
        'error': error,
        'l_site_messages': site_messages(request),
        'css': css,
        'no_loader': no_loader,
    })


def all_songs_all_lyrics(request, animation_id):
    animation = Animation.get_animation_by_id_without_group_id(int(animation_id))

    if not animation:
        return redirect('homepage')
    
    animation.all_songs()
    full_title = animation.name
    lyrics = ''
    song_params = get_song_params(request)

    for idx, song in enumerate(animation.songs):
        song_info = Song(song['song_id'])
        song_info.verse_max_lines = song_params['verse_max_lines']
        song_info.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
        song_info.get_verses()
        lyrics += f'''
    <hr>
    <section id="song-{idx}">
        <h2>{song['full_title']}</h2>
        <p>{song_info.get_lyrics_to_display(False, Site=Site(getattr(request, "LANGUAGE_CODE", None)))}</p>
    </section>'''
        
    # QR-CODE
    img_qr_code = ''
    try:
        link_to_copy = f'https://www.carthographie.fr/animations/lyrics_slide_show/all_lyrics/{animation_id}/'
        
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(link_to_copy)
        qr.make(fit=True)
        img = qr.make_image(fill_color="white", back_color="black")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_qr_code = base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        error = "[ERR35]"

    
    return render(request, 'app_animation/all_lyrics.html', {
        'full_title': full_title,
        'lyrics': lyrics,
        'link_to_copy': link_to_copy,
        'img_qr_code': img_qr_code,
    })


def _client_ip(request: HttpRequest) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", ""))

def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

def _random_filename(original_name: str) -> str:
    ext = Path(original_name).suffix.lower()
    token = secrets.token_hex(5)  # ex: djhekghdke
    return f"{token}{ext}"

@login_required
@require_http_methods(["GET", "POST"])
def submit_image(request: HttpRequest) -> HttpResponse:
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        if group != 0:
            group_selected = group.name


    description = (request.POST.get("txt_description") or "").strip()
    
    if request.method == "POST" and "btn_save" in request.POST:
        uploaded = request.FILES.get("img_file")
        if not uploaded:
            error = "[ERR52]"
        else:
            cfg = get_image_params(request)
            error = utils.validate_image(uploaded, cfg)

            if not error:
                temp_dir = _ensure_dir(Path(settings.IMG_TEMP_DIR))
                filename = _random_filename(uploaded.name)
                dest_path = temp_dir / filename

                with dest_path.open("wb") as fh:
                    for chunk in uploaded.chunks():
                        fh.write(chunk)

                rel_path = str(dest_path.relative_to(Path(settings.MEDIA_ROOT)))
                user_id: Optional[int] = request.user.id if request.user.is_authenticated else None
                ip = _client_ip(request)

                try:
                    with Image.open(dest_path) as im:
                        width, height = im.size
                except Exception as e:
                    width, height = 0, 0

                submission = BackgroundImageSubmission(
                    stored_path=rel_path,
                    original_name=uploaded.name[:255],
                    mime=uploaded.content_type,
                    size_bytes=int(uploaded.size),
                    width=width,
                    height=height,
                    description=description[:200]
                )
                if submission.save():
                    return render(request, "app_animation/submit_image_ok.html", {
                        'group_selected': group_selected,
                        'error': error,
                        'l_site_messages': site_messages(request),
                        'css': css,
                        'no_loader': no_loader,
                    })
                else:
                    error = "[ERR60]"

    return render(request, "app_animation/submit_image.html", {
        'group_selected': group_selected,
        'error': error,
        'l_site_messages': site_messages(request),
        'css': css,
        'no_loader': no_loader,
    })            
            

# Remove DB entries for images not present in img_dir
def _sync_images_with_db(img_dir: Path, db_table: str):
    """
    Synchronize images in img_dir with db_table.
    - Add/update DB entries for images present in img_dir.
    - Remove DB entries for images missing from img_dir.
    """
    files_in_dir = list(img_dir.glob("*"))
    
    # Update or insert images in DB
    for file_path in files_in_dir:
        try:
            with Image.open(file_path) as im:
                width, height = im.size
            size_bytes = file_path.stat().st_size
            mime = Image.MIME.get(im.format, "application/octet-stream")
        except Exception:
            width, height, size_bytes, mime = 0, 0, 0, "application/octet-stream"

        rel_img_dir = str(img_dir.relative_to(settings.MEDIA_ROOT))
        file_path_name = str(img_dir).split("media/")[1] + "/" + file_path.name
        if db_table == 'l_image_submissions':
            if not BackgroundImageSubmission.image_exists(stored_path=file_path_name):
                # create image
                submission = BackgroundImageSubmission(
                    stored_path=file_path_name,
                    original_name="new INSERT",
                    mime=mime,
                    size_bytes=size_bytes,
                    width=width,
                    height=height,
                    description=""
                )
                submission.save()
            else:
                image = BackgroundImageSubmission(stored_path=file_path_name)
                image.hydrate()
                # Compare and update if necessary
                image = BackgroundImageSubmission(stored_path=file_path_name)
                image.hydrate()
                if image.mime != mime or image.size_bytes != size_bytes or image.width != width or image.height != height:
                    image.mime = mime
                    image.size_bytes = size_bytes
                    image.width = width
                    image.height = height
                    image.save()
        elif db_table == 'l_image_backgrounds':
            if not BackgroundImage.image_exists(stored_path=file_path_name):
                # create image
                bg_image = BackgroundImage(
                    stored_path=file_path_name,
                    mime=mime,
                    size_bytes=size_bytes,
                    width=width,
                    height=height,
                    description=""
                )
                bg_image.save()
            else:
                image = BackgroundImage(stored_path=file_path_name)
                image.hydrate()
                # Compare and update if necessary
                image = BackgroundImage(stored_path=file_path_name)
                image.hydrate()
                if image.mime != mime or image.size_bytes != size_bytes or image.width != width or image.height != height:
                    image.mime = mime
                    image.size_bytes = size_bytes
                    image.width = width
                    image.height = height
                    image.save()

def _delete_db_image_without_image_file(img_dir: Path, db_table: str):
    if db_table == "l_image_submissions":
        image_list = BackgroundImageSubmission.get_submissions()
    elif db_table == "l_image_backgrounds":
        image_list = BackgroundImage.get_backgrounds()
    else:
        return

    files_in_dir = list(img_dir.glob("*"))

    for image in image_list:
        stored_path = image['stored_path']
        to_delete = True
        for file in files_in_dir:
            stored_path_file = str(img_dir).split("media/")[0] + "media/" + stored_path
            if str(file) == stored_path_file: to_delete = False
        
        if db_table == "l_image_submissions":
            if to_delete: BackgroundImageSubmission.delete_by_stored_path(stored_path)
        elif db_table == "l_image_backgrounds":
            if to_delete: BackgroundImage.delete_by_stored_path(stored_path)

def _clean_submissions_and_images():
    """
    Synchronize both temp and validated image directories with their respective DB tables.
    """
    # Temp submissions folder
    temp_dir = Path(settings.IMG_TEMP_DIR)
    _sync_images_with_db(temp_dir, "l_image_submissions")
    _delete_db_image_without_image_file(temp_dir, "l_image_submissions")

    # Validated images folder
    validated_dir = Path(settings.IMG_VALIDATED_DIR)
    _sync_images_with_db(validated_dir, "l_image_backgrounds")
    _delete_db_image_without_image_file(validated_dir, "l_image_backgrounds")

@login_required
def get_submissions(request):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    _clean_submissions_and_images()

    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        if group != 0:
            group_selected = group.name
    
    if not is_moderator(request):
        return redirect('animations')
    
    if request.method == "POST":
        stored_path = request.POST.getlist("stored_path")

        if 'btn_validate' in request.POST:
            image_tmp = BackgroundImageSubmission(stored_path=stored_path)
            image_tmp.hydrate()
            
            image_validated = BackgroundImage(
                stored_path=str(image_tmp.stored_path).replace("/tmp/", "/validated/"),
                image_id=0,
                mime=image_tmp.mime,
                size_bytes=image_tmp.size_bytes,
                width=image_tmp.width,
                height=image_tmp.height,
                description=request.POST.get("txt_moderation_description", "")[:200]
            )

            try:
                src = Path(settings.MEDIA_ROOT) / image_tmp.stored_path[0].lstrip("/")
                dest = Path(settings.MEDIA_ROOT) / image_tmp.stored_path[0].replace("/tmp/", "/validated/").lstrip("/")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                image_validated.save()
            except Exception as e:
                error = "Error moving file"


        if 'btn_invalidate' in request.POST:
            image_tmp = BackgroundImageSubmission(stored_path=stored_path)
            image_tmp.hydrate()
            src = Path(settings.MEDIA_ROOT) / image_tmp.stored_path[0].lstrip("/")
            if src.exists(): src.unlink()

        _clean_submissions_and_images()
            
    
    submission_list = BackgroundImageSubmission.get_submissions()
    if not submission_list:
        return redirect('animations')

    return render(request, "app_animation/get_submissions.html", {
        'group_selected': group_selected,
        'error': error,
        'submission_list': submission_list,
        'l_site_messages': site_messages(request),
        'css': css,
        'no_loader': no_loader,
        'pending_submissions_count': BackgroundImageSubmission.pending_submissions_count(),
    })


@login_required
def moderate_images(request):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        if group != 0:
            group_selected = group.name
    
    if not is_moderator(request):
        return redirect('animations')
    
    _clean_submissions_and_images()

    if request.method == "POST":
        image = BackgroundImage(stored_path=request.POST.get("txt_stored_path", ""))
        image.hydrate()
        if 'btn_activate' in request.POST:
            image.status = "ACTIVED"
            image.save()
        if 'btn_unactivate' in request.POST:
            image.status = "UNACTIVED"
            image.save()
        if 'btn_delete' in request.POST:
            img_path = Path(settings.MEDIA_ROOT) / image.stored_path.lstrip("/")
            if img_path.exists(): img_path.unlink()
            BackgroundImage.delete_by_stored_path(image.stored_path)

    background_images = BackgroundImage.get_backgrounds()

    return render(request, "app_animation/moderate_images.html", {
        'group_selected': group_selected,
        'error': error,
        'background_images': background_images,
        'l_site_messages': site_messages(request),
        'css': css,
        'no_loader': no_loader,
    })


@login_required
def modify_BG_image_animation(request, xxx_id=None):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    if "modify_BG_image_animation" in request.resolver_match.url_name:
        target = 'animation'
        animation_id = xxx_id
    elif "modify_BG_image_song" in request.resolver_match.url_name:
        target = 'song'
        animation_id = Animation.get_animation_id_by_song_id(xxx_id)
    elif "modify_BG_image_verse" in request.resolver_match.url_name:
        target = 'verse'
        verse_id = int(request.GET.get('verse_id', 0))
        animation_id = Animation.get_animation_id_by_verse_id(xxx_id, verse_id)

    animation = None
    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        group_selected = group.name
    
    if group_selected:
        animation = Animation.get_animation_by_id(animation_id, group_id)
        if not animation:
            return redirect('animations')

        if request.method == 'POST':
            if 'btn_return' in request.POST:
                return redirect('modify_animation', animation_id=animation_id)
            pass
            # if 'btn_del_song_colors' in request.POST:
            #     animation.update_animation_song_colors(xxx_id, None, None)
            # elif 'btn_del_verse_colors' in request.POST:
            #     animation.update_animation_verse_colors(xxx_id, verse_id, None, None)
            # elif 'btn_save' in request.POST:
            #     if target == 'animation':
            #         animation.color_rgba = request.POST.get('text_color')
            #         animation.bg_rgba = request.POST.get('bg_color')
            #         animation.save()
            #     elif target == 'song':
            #         animation.update_animation_song_colors(xxx_id, request.POST.get('text_color'), request.POST.get('bg_color'))
            #     elif target == 'verse':
            #         animation.update_animation_verse_colors(xxx_id,
            #                                                 verse_id,
            #                                                 request.POST.get('text_color'),
            #                                                 request.POST.get('bg_color'))
            # animation = Animation.get_animation_by_id(animation_id, group_id)
            # return redirect('modify_animation', animation_id=animation_id)

    bg_images = BackgroundImage.get_backgrounds(status_filter="ACTIVED")

    return render(request, 'app_animation/modify_BG_image_animation.html', {
        'animation': animation,
        'target': target,
        'bg_images': bg_images,
        'group_selected': group_selected,
        'error': error,
        'l_site_messages': site_messages(request),
        'css': css,
        'no_loader': no_loader,
    })