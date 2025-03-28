from django.shortcuts import render
from .SQL_group import Group
import hashlib



def groups(request):
    error = ''

    if request.method == 'POST':

        if request.method == 'POST':
            new_group = Group(
                            name = request.POST.get('txt_new_name')
                           )
            new_group.save()
            request.POST = request.POST.copy()
            request.POST['txt_new_name'] = ''

    groups = Group.get_all_groups


    return render(request, 'app_group/groups.html', {
        'groups': groups,
        # 'title': request.POST.get('txt_new_title', ''),
        # 'description': request.POST.get('txt_new_description', ''),
        'error': error,
        })


def add_group(request):
    error = ''
    name = ''
    info = ''
    admin_email = ''
    valided = ''

    if request.method == 'POST':
        if request.POST.get('btn_new_group'):
            name = request.POST.get('txt_new_name')
            info = ''
            admin_email = ''

        elif request.POST.get('btn_add_group'):
            name = request.POST.get('txt_new_name')
            info = request.POST.get('txt_new_info')
            admin_email = request.POST.get('txt_new_admin_email')
            txt_new_admin_password = request.POST.get('txt_new_admin_password')
            txt_new_admin_password_confirm = request.POST.get('txt_new_admin_password_confirm')

            if name.strip() == '':
                error = 'Group name is required'
            else:
                if txt_new_admin_password != txt_new_admin_password_confirm:
                    error = 'Password and confirm password do not match'
                else:
                    hashed_password = hashlib.md5(txt_new_admin_password.encode()).hexdigest()
                    new_group = Group(
                        name=name,
                        info=info,
                        admin_email=admin_email,
                        admin_password=hashed_password
                    )
                    new_group.save()
                    valided = 'Groupe enregistré'


    return render(request, 'app_group/add_group.html', {
        'name': name,
        'info': info,
        'admin_email': admin_email,
        'valided': valided,
        'error': error,
        })