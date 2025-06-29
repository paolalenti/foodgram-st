import json
from channels.generic.websocket import AsyncWebsocketConsumer


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = "chat_room"
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
        data = json.loads(text_data)
        message = data.get("message", "")

        # Получаем пользователя
        user = self.scope["user"]
        user_label = user.email if user.is_authenticated else "Anonymous"

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "user": user_label
            }
        )

    async def chat_message(self, event):
        message = event["message"]
        user = event["user"]
        await self.send(text_data=json.dumps({
            "message": message,
            "user": user
        }))


class UserStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_group = "user_status"
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )
        await self.accept()

        # Отправка уведомления о подключении
        user = self.scope["user"]
        user_label = user.email if user.is_authenticated else "Anonymous"
        await self.channel_layer.group_send(
            self.user_group,
            {
                "type": "user_joined",
                "user": user_label
            }
        )

    async def disconnect(self, close_code):
        # Отправка уведомления об отключении
        user = self.scope["user"]
        user_label = user.email if user.is_authenticated else "Anonymous"
        await self.channel_layer.group_send(
            self.user_group,
            {
                "type": "user_left",
                "user": user_label
            }
        )
        await self.channel_layer.group_discard(
            self.user_group,
            self.channel_name
        )

    async def user_joined(self, event):
        user = event["user"]
        await self.send(text_data=json.dumps({
            "status": "joined",
            "user": user
        }))

    async def user_left(self, event):
        user = event["user"]
        await self.send(text_data=json.dumps({
            "status": "left",
            "user": user
        }))
