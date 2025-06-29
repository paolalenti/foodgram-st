from django.db.models.signals import post_save
from django.dispatch import receiver
from recipes.models import Recipe
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@receiver(post_save, sender=Recipe)
def send_recipe_notification(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "notifications",
            {
                "type": "send_notification",
                "message": f"Новый рецепт: {instance.name}"
            }
        )