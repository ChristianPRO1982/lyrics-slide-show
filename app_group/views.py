from django.shortcuts import render
from django.contrib.auth.models import User
from .SQL_group import Group



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
        })