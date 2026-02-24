from django.test import TestCase, Client

# Create your tests here.

from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Room, Message

User = get_user_model()

class BaseTestCase(TestCase):
    """Shared setup for all tests."""

    def setUp(self):
        self.client = Client() # Create users

        self.creator = User.objects.create_user(username='creator', password='pass123')
        self.member = User.objects.create_user(username='member', password='pass123')
        self.outsider = User.objects.create_user(username='outsider', password='pass123')

        self.room = Room.objects.create(  # Create a room
            name='Test Room',
            slug='test-room',
            creator=self.creator
        )
        self.room.members.add(self.member)

# AUTHENTICATION TESTS

class AuthenticationTests(BaseTestCase):

    def test_unauthenticated_user_redirected_from_room_list(self):
        response = self.client.get(reverse('chat:room_list'))
        self.assertRedirects(response, '/accounts/login/?next=/')

    def test_unauthenticated_user_redirected_from_room(self):
        response = self.client.get(reverse('chat:room', kwargs={'slug': self.room.slug}))
        self.assertRedirects(response, f'/accounts/login/?next=/rooms/{self.room.slug}/')
    
    async def test_unauthenticated_user_cannot_connect(self):
        from django.contrib.auth.models import AnonymousUser
        communicator = WebsocketCommunicator(application, f'/ws/rooms/{self.room.slug}/')
        communicator.scope['user'] = AnonymousUser()
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

# ROOM ACCESS TESTS

class RoomAccessTests(BaseTestCase):

    def test_creator_can_access_room(self):
        self.client.login(username='creator', password='pass123')
        response = self.client.get(reverse('chat:room', kwargs={'slug': self.room.slug}))
        self.assertEqual(response.status_code, 200)

    def test_member_can_access_room(self):
        self.client.login(username='member', password='pass123')
        response = self.client.get(reverse('chat:room', kwargs={'slug': self.room.slug}))
        self.assertEqual(response.status_code, 200)

    def test_outsider_cannot_access_room(self):
        self.client.login(username='outsider', password='pass123')
        response = self.client.get(reverse('chat:room', kwargs={'slug': self.room.slug}))
        self.assertRedirects(response, reverse('chat:room_list'))

    def test_room_list_only_shows_accessible_rooms(self): # Create a room outsider isn't part of
        other_room = Room.objects.create(
            name='Private Room',
            slug='private-room',
            creator=self.creator
        )
        self.client.login(username='outsider', password='pass123')
        response = self.client.get(reverse('chat:room_list'))
        rooms = list(response.context['rooms'])
        self.assertNotIn(other_room, rooms)
        self.assertNotIn(self.room, rooms)

    def test_outsider_sees_no_rooms(self):
        self.client.login(username='outsider', password='pass123')
        response = self.client.get(reverse('chat:room_list'))
        self.assertEqual(list(response.context['rooms']), [])

# MESSAGING TESTS

from channels.testing import WebsocketCommunicator
from chatproject.asgi import application

class MessagingTests(BaseTestCase):

    async def test_member_can_send_message(self):
        communicator = WebsocketCommunicator(application, f'/ws/rooms/{self.room.slug}/')
        communicator.scope['user'] = self.member
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to({'content': 'Hello world'})
        response = await communicator.receive_json_from()

        self.assertEqual(response['content'], 'Hello world')
        self.assertEqual(response['user'], self.member.username)
        await communicator.disconnect()

    async def test_outsider_cannot_connect_to_send(self):
        communicator = WebsocketCommunicator(application, f'/ws/rooms/{self.room.slug}/')
        communicator.scope['user'] = self.outsider
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_empty_message_not_broadcast(self):
        communicator = WebsocketCommunicator(application, f'/ws/rooms/{self.room.slug}/')
        communicator.scope['user'] = self.member
        await communicator.connect()

        await communicator.send_json_to({'content': '   '})  # whitespace only

        response = await communicator.receive_nothing(timeout=1) # Should receive nothing back
        self.assertTrue(response)
        await communicator.disconnect()

    async def test_message_saved_to_db(self):
        from channels.db import database_sync_to_async
        from .models import Message

        communicator = WebsocketCommunicator(application, f'/ws/rooms/{self.room.slug}/')
        communicator.scope['user'] = self.member
        await communicator.connect()

        await communicator.send_json_to({'content': 'persisted?'})
        await communicator.receive_json_from()  # wait for broadcast

        count = await database_sync_to_async(
            Message.objects.filter(room=self.room, content='persisted?').count
        )()
        self.assertEqual(count, 1)
        await communicator.disconnect()

# MEMBER MANAGE TESTS

class MemberManagementTests(BaseTestCase):

    def test_creator_can_add_member(self):
        self.client.login(username='creator', password='pass123')
        self.client.post(
            reverse('chat:members_view', kwargs={'slug': self.room.slug}),
            {'action': 'add', 'user_id': self.outsider.id}
        )
        self.assertIn(self.outsider, self.room.members.all())

    def test_creator_can_remove_member(self):
        self.client.login(username='creator', password='pass123')
        self.client.post(
            reverse('chat:members_view', kwargs={'slug': self.room.slug}),
            {'action': 'remove', 'user_id': self.member.id}
        )
        self.assertNotIn(self.member, self.room.members.all())

    def test_member_cannot_add_others(self):
        self.client.login(username='member', password='pass123')
        self.client.post(
            reverse('chat:members_view', kwargs={'slug': self.room.slug}),
            {'action': 'add', 'user_id': self.outsider.id}
        )
        self.assertNotIn(self.outsider, self.room.members.all()) # POST should be ignored for non-creators

    def test_outsider_cannot_access_members_view(self):
        self.client.login(username='outsider', password='pass123')
        response = self.client.get(
            reverse('chat:members_view', kwargs={'slug': self.room.slug})
        )
        self.assertRedirects(response, reverse('chat:room_list'))

# ROOM MANAGE TESTS

class RoomManagementTests(BaseTestCase):

    def test_creator_can_delete_room(self):
        self.client.login(username='creator', password='pass123')
        self.client.post(reverse('chat:delete_room', kwargs={'slug': self.room.slug}))
        self.assertFalse(Room.objects.filter(slug='test-room').exists())

    def test_member_cannot_delete_room(self):
        self.client.login(username='member', password='pass123')
        self.client.post(reverse('chat:delete_room', kwargs={'slug': self.room.slug}))
        self.assertTrue(Room.objects.filter(slug='test-room').exists())

    def test_room_deletion_cascades_messages(self):
        Message.objects.create(user=self.creator, room=self.room, content='test')
        self.client.login(username='creator', password='pass123')
        self.client.post(reverse('chat:delete_room', kwargs={'slug': self.room.slug}))
        self.assertEqual(Message.objects.filter(room=self.room).count(), 0)

    def test_slug_collision_handling(self):
        self.client.login(username='creator', password='pass123')

        Room.objects.create(
            name='Slug Test',
            slug='slug-test',
            creator=self.creator
        )
        self.client.post(reverse('chat:create_room'), {'name': 'Slug Test 2'})

        Room.objects.create(name='Collision A', slug='collision', creator=self.creator)
        Room.objects.create(name='Collision B', slug='collision-1', creator=self.creator)

        self.client.post(reverse('chat:create_room'), {'name': 'Collision'})
        self.assertTrue(Room.objects.filter(slug='collision-2').exists())

# WEBSOCKET TESTS

from channels.testing import WebsocketCommunicator
from chatproject.asgi import application

class WebSocketTests(BaseTestCase):

    async def test_authenticated_member_can_connect(self):
        communicator = WebsocketCommunicator(
            application,
            f'/ws/rooms/{self.room.slug}/'
        )
        # Simulate authenticated user in scope
        communicator.scope['user'] = self.member
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_outsider_cannot_connect(self):
        communicator = WebsocketCommunicator(
            application,
            f'/ws/rooms/{self.room.slug}/'
        )
        communicator.scope['user'] = self.outsider
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_unauthenticated_user_cannot_connect(self):
        from django.contrib.auth.models import AnonymousUser
        communicator = WebsocketCommunicator(
            application,
            f'/ws/rooms/{self.room.slug}/'
        )
        communicator.scope['user'] = AnonymousUser()
        connected, _ = await communicator.connect()
        self.assertFalse(connected)