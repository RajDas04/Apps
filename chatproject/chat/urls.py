from django.urls import path
from . import views

app_name = 'chat'
urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('', views.room_list, name='room_list'),
    path('rooms/create/', views.create_room, name='create_room'),
    path('rooms/<slug:slug>/', views.room_view, name='room'),
    # path('rooms/<slug:slug>/messages-json/', views.room_messages_json, name='room_messages_json'),
    # path('rooms/<slug:slug>/post-message/', views.room_post_message, name='room_post_message'),
    path('rooms/<slug:slug>/manage/', views.members_view, name='members_view'),
    path('rooms/<slug:slug>/delete/', views.delete_room, name='delete_room'),
]

# Messeges cannot be sent