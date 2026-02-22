from .models import Room, Message
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.slug = self.scope['url_route']['kwargs']['slug']
        self.room_group_name = f'chat_{self.slug}'
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return
        
        has_access = await self.check_access()
        if not has_access:
            await self.close()
            return
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Called when the browser sends a message over the WebSocket."""
        data = json.loads(text_data)
        content = data.get('content', '').strip()

        if not content:
            return
        
        message = await self.save_message(content) # save to db

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'id': message.id,
                'user': self.user.username,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
            }
        )
    
    async def chat_message(self, event):
        """Its called when a message is sent to the group."""
        await self.send(text_data=json.dumps({
            'id': event['id'],
            'user': event['user'],
            'content': event['content'],
            'created_at': event['created_at'],
        }))


    @database_sync_to_async
    def check_access(self):
        try:
            room = Room.objects.get(slug=self.slug)
            return (
                self.user == room.creator or
                room.members.filter(id=self.user.id).exists()
            )

        except Room.DoesNotExist:
            return False
        
    @database_sync_to_async
    def save_message(self, content):
        room = Room.objects.get(slug=self.slug)
        return Message.objects.create(
            room=room,
            user=self.user,
            content=content
        )