from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
import qrcode
from io import BytesIO
import base64
import uuid
from .SQL_group import Group
from app_main.utils import is_no_loader, is_moderator



def groups(request):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    group_selected = ''

    if request.method == 'POST':
        new_group = Group(name = request.POST.get('txt_new_name'))
        new_group.save()
        request.POST = request.POST.copy()
        request.POST['txt_new_name'] = ''

    groups = Group.get_all_groups

    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        if group != 0:
            group_selected = group.name


    return render(request, 'app_group/groups.html', {
        'groups': groups,
        'group_selected': group_selected,
        'error': error,
        'css': css,
        'no_loader': no_loader,
        })


def select_group(request, group_id):
    url_token = ''
    username = request.user.username
    
    group = Group.get_group_by_id(group_id, url_token, username, is_moderator(request))
    
    if group is None: group_id = ''
    if group == 0: group_id = ''
        
    request.session['group_id'] = group_id
    request.session['url_token'] = url_token

    return redirect('groups')


def select_group_by_token(request, group_id, url_token):
    username = request.user.username

    group = Group.get_group_by_id(group_id, url_token, username, is_moderator(request))

    if group is None or group == 0:
        group_id = ''
        url_token = ''
        
    request.session['group_id'] = group_id
    request.session['url_token'] = url_token

    return redirect('groups')


@login_required
def add_group(request):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    name = ''
    info = ''
    username = ''
    valided = ''

    if request.method == 'POST':
        if request.POST.get('btn_new_group'):
            name = request.POST.get('txt_new_name')
            info = ''
            username = request.user.username

        elif request.POST.get('btn_add_group'):
            name = request.POST.get('txt_new_name')
            info = request.POST.get('txt_new_info')
            username = request.POST.get('txt_username')

            if name.strip() == '':
                error = '[ERR3]'
            elif not User.objects.filter(username=username).exists():
                error = '[ERR4]'
            else:
                new_group = Group(
                    name=name,
                    info=info
                )
                error = new_group.save()
                if error == '':
                    error =new_group.add_admin(username, 1)
                    valided = 'Groupe enregistré'


    return render(request, 'app_group/add_group.html', {
        'name': name,
        'info': info,
        'username': username,
        'valided': valided,
        'error': error,
        'css': css,
        'no_loader': no_loader,
        })


@login_required
def modify_group(request, group_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)
    
    url_token = ''
    username = request.user.username

    group = Group.get_admin_group_by_id(group_id, username, is_moderator(request))
    print("GROUP ID", group_id, group.group_id)
    group_url = ''
    qr_code_base64 = ''
    list_of_members = []
    
    if group is None:
        error = '[ERR11]'
    elif group == 0:
        error = '[ERR10]'
    else:
        if request.method == 'POST':
            if 'btn_cancel' not in request.POST:
                required_fields = {'box_group_delete', 'box_group_delete_confirm'}
                if required_fields.issubset(request.POST):
                    if group.delete_group():
                        return redirect('groups')
                    else:
                        error = '[ERR24]'

                group.name = request.POST.get('txt_group_name')
                group.info = request.POST.get('txt_group_info')

                if request.POST.get('box_group_private') is not None:
                    group.private = 1
                else:
                    group.private = 0

                if request.POST.get('box_group_token') is not None:
                    group.token = str(uuid.uuid4())
                if request.POST.get('box_group_token_delete') is not None:
                    group.token = ''

                group.save()

            else:
                return redirect('groups')
    
        if group.token != '':
            group_url = f"{request.scheme}://{request.get_host()}/groups/{group.group_id}/{group.token}"
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(group_url)
            qr.make(fit=True)

            # Create an image from the QR Code instance
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert the image to a base64 string
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            buffer.close()
        
        list_of_members = group.get_list_of_members()

    return render(request, 'app_group/modify_group.html', {
        'group': group,
        'group_url': group_url,
        'group_url_qr': qr_code_base64,
        'list_of_members': list_of_members,
        'error': error,
        'css': css,
        'no_loader': no_loader,
        })