from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand

from app_animation.services.remote_sessions import purge_expired_remote_connections


class Command(BaseCommand):
    help = "Remove expired remote WebSocket leases."

    def handle(self, *args, **options):
        del args, options
        result = purge_expired_remote_connections()
        channel_layer = get_channel_layer()
        for session_id in result.master_unavailable_session_ids:
            async_to_sync(channel_layer.group_send)(
                f"lss.remote.{session_id.hex}",
                {"type": "remote.master.unavailable"},
            )
        for update in result.updates:
            if update.remote_count_changed and update.master_channel_name:
                async_to_sync(channel_layer.send)(
                    update.master_channel_name,
                    {
                        "type": "remote.connection.count",
                        "count": update.remote_connection_count,
                    },
                )
        if result.removed_count:
            self.stdout.write(
                f"Purged {result.removed_count} expired remote connection(s)."
            )
