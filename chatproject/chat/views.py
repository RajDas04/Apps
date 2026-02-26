from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from .models import Room
from .forms import MessageForm, RoomForm
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Q

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
    """Show all available chat rooms where the user is memeber or creator."""
    rooms = Room.objects.filter(Q(creator= request.user) | Q(members= request.user)).distinct()
    return render(request, 'room_list.html', {'rooms': rooms})


@login_required
def room_view(request, slug):
    room = get_object_or_404(Room, slug=slug)
    if request.user != room.creator and request.user not in room.members.all():
        return redirect('chat:room_list')

    form = MessageForm()

    messages = room.messages.select_related('user')
    return render(request, 'room.html', {
        'room': room,
        'messages': messages,
        'form': form,
    })

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
    member_ids = set(room.members.values_list('id', flat=True))

    return render(request, 'manage_members.html', {
        'room': room,
        'users': users,
        'is_creator': is_creator,
        'member_ids': member_ids,
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

    return redirect('chat:members_view', slug=room.slug)
