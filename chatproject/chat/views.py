from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Room
from .forms import MessageForm, RoomForm
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.utils.dateformat import format

User = get_user_model()

def signup(request):
    """Handle user registration."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect('chat:room_list')  # redirect to room list
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})


@login_required
def room_list(request):
    """Show all available chat rooms."""
    rooms = Room.objects.all()
    return render(request, 'room_list.html', {'rooms': rooms})


@login_required
def room_view(request, slug):
    room = get_object_or_404(Room, slug=slug)
    if request.user != room.creator and request.user not in room.members.all():
        return redirect('chat:room_list')

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.user = request.user
            msg.room = room
            msg.save()
            return redirect('chat:room', slug=room.slug)
    else:
        form = MessageForm()

    messages = room.messages.select_related('user')
    return render(request, 'room.html', {
        'room': room,
        'messages': messages,
        'form': form,
    })

@login_required
def room_messages_json(request, slug):
    room = get_object_or_404(Room, slug=slug)
    if request.user != room.creator and request.user not in room.members.all():
        return JsonResponse({'error': 'Not allowed'}, status=403)
    last_id = int(request.GET.get('last_id', 0))
    qs = room.messages.filter(id__gt=last_id).select_related('user').order_by('created_at')
    data = {
        "messages": [
            {"id": m.id, "user": m.user.username, "content": m.content,"created_at": format(m.created_at, "M d, Y, P"),}
            for m in qs]}
    return JsonResponse(data)

#Handle AJAX POST
@login_required
@require_POST
def room_post_message(request, slug):
    room = get_object_or_404(Room, slug=slug)

    if request.user != room.creator and request.user not in room.members.all():
        return JsonResponse({'error': 'Not allowed'}, status=403)

    form = MessageForm(request.POST)
    if form.is_valid():
        msg = form.save(commit=False)
        msg.user = request.user
        msg.room = room
        msg.save()
        return JsonResponse({
            'id': msg.id,
            'user': msg.user.username,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
        })
    return JsonResponse({'errors': form.errors}, status=400)

@login_required
def create_room(request):
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.creator = request.user
            base_slug = slugify(room.name)
            slug = base_slug
            counter = 1
            while Room.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            room.slug = slug
            room.save()
            return redirect('chat:room', slug=room.slug)
    else:
        form = RoomForm()
    return render(request, 'create_room.html', {'form': form})

@login_required
def members_view(request, slug):
    room = get_object_or_404(Room, slug=slug)

    if request.user != room.creator and request.user not in room.members.all():
        return redirect('chat:room_list')

    is_creator = (request.user == room.creator)

    if is_creator and request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')

        if action == 'delete':
            room_name = room.name
            room.delete()
            messages.success(request, f'Room "{room_name}" was deleted successfully.')
            return redirect('chat:room_list')

        if user_id:
            target = get_object_or_404(User, id=user_id)
            if action == 'add':
                room.members.add(target)
                messages.success(request, f'{target.username} added to the room.')
            elif action == 'remove':
                room.members.remove(target)
                messages.info(request, f'{target.username} removed from the room.')
    users = User.objects.exclude(id=room.creator.id)

    return render(request, 'manage_members.html', {
        'room': room,
        'users': users,
        'is_creator': is_creator,
    })


@login_required
def delete_room(request, slug):
    room = get_object_or_404(Room, slug=slug)
    if request.user != room.creator:
        return redirect('chat:room', slug=room.slug)

    if request.method == 'POST':
        room_name = room.name
        room.delete()
        messages.success(request, f'Room "{room_name}" was deleted successfully.')
        return redirect('chat:room_list')

    return render(request, 'chat:manage_members', slug=room.slug)
