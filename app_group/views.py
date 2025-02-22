from django.shortcuts import render
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