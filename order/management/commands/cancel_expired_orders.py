from django.core.management.base import BaseCommand
from order.tasks import cancel_expired_pending_orders


class Command(BaseCommand):
    help = 'Cancel orders that have been pending payment for more than 1 hour'

    def handle(self, *args, **options):
        self.stdout.write('Starting auto-cancellation of expired pending orders...')
        
        result = cancel_expired_pending_orders()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully cancelled {result["cancelled_orders"]} orders, '
                f'released {result["stock_released"]} items back to inventory'
            )
        )