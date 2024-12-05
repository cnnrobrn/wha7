
"""Message handling service for the Wha7 application.

This service manages all asynchronous message processing including:
- SMS handling via Twilio
- Queue management with Azure Service Bus
- Notification dispatch and tracking
- Message templating and formatting

Note: This service coordinates with but doesn't duplicate social media
message handling, which is managed by the SocialMediaService.
"""

from typing import Optional, Dict, Any, List
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException
from fastapi import BackgroundTasks
import json
import asyncio
from datetime import datetime

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.ai_processing import AIService
from app.services.image_processing import ImageProcessingService
from app.models.database.user import PhoneNumber

# Initialize components
logger = get_logger(__name__)
settings = get_settings()

class MessageTemplates:
    """Message templates for different notification types."""
    
    OUTFIT_ANALYSIS = """
    {response}
    
    Items found:
    {items}
    
    View full details: {app_link}
    """
    
    WELCOME = """
    Welcome to Wha7! 👋
    
    Share fashion screenshots or photos, and I'll help you find similar items.
    """
    
    ERROR = """
    Sorry, I encountered an issue processing your request. Please try again.
    """

class MessageService:
    """Service for handling message processing and notifications."""
    
    def __init__(
        self,
        ai_service: AIService,
        image_service: ImageProcessingService
    ):
        """Initialize service with required dependencies."""
        # Initialize Azure Service Bus
        self.servicebus_client = ServiceBusClient.from_connection_string(
            settings.SERVICEBUS_CONNECTION_STRING
        )
        
        # Initialize Twilio
        self.twilio_client = TwilioClient(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        
        # Store service dependencies
        self.ai_service = ai_service
        self.image_service = image_service
        
        # Queue names
        self.notification_queue = settings.NOTIFICATION_QUEUE
        self.sms_queue = settings.SMS_QUEUE
    
    async def process_sms_message(
        self,
        from_number: str,
        message_text: Optional[str] = None,
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process incoming SMS message.
        
        Note: This complements the social endpoint SMS handling by
        managing the actual message processing and response generation.
        """
        try:
            # Process media if present
            if media_url:
                # Download and process image
                image_data = await self.image_service.process_url(media_url)
                
                # Analyze with AI
                analysis = await self.ai_service.analyze_outfit_image(
                    image_data=image_data,
                    message_text=message_text
                )
                
                # Generate response
                response = self._format_outfit_response(analysis)
                
                # Queue notification for processing
                await self._queue_notification(
                    phone_number=from_number,
                    notification_type="outfit_analysis",
                    data={
                        "analysis": analysis,
                        "response": response
                    }
                )
                
                return {"response": response}
            
            else:
                # Handle text-only message
                return {"response": MessageTemplates.ERROR}
                
        except Exception as e:
            logger.error("SMS processing failed", error=e)
            await self._queue_notification(
                phone_number=from_number,
                notification_type="error",
                data={"error": str(e)}
            )
            return {"response": MessageTemplates.ERROR}
    
    async def start_message_processing(self):
        """Start processing messages from Azure Service Bus queues."""
        async with self.servicebus_client:
            # Process notifications
            notification_processor = self.servicebus_client.get_queue_receiver(
                queue_name=self.notification_queue
            )
            
            # Process SMS messages
            sms_processor = self.servicebus_client.get_queue_receiver(
                queue_name=self.sms_queue
            )
            
            async with notification_processor, sms_processor:
                # Process both queues concurrently
                await asyncio.gather(
                    self._process_notifications(notification_processor),
                    self._process_sms_queue(sms_processor)
                )
    
    async def _process_notifications(self, processor):
        """Process messages from notification queue."""
        async for msg in processor:
            try:
                # Parse notification data
                notification = json.loads(str(msg))
                
                # Process based on type
                if notification['type'] == 'outfit_analysis':
                    await self._send_sms(
                        to_number=notification['phone_number'],
                        message=self._format_outfit_response(
                            notification['data']['analysis']
                        )
                    )
                
                # Complete the message
                await msg.complete()
                
            except Exception as e:
                logger.error("Notification processing failed", error=e)
                await msg.abandon()
    
    async def _process_sms_queue(self, processor):
        """Process messages from SMS queue."""
        async for msg in processor:
            try:
                # Parse SMS data
                sms_data = json.loads(str(msg))
                
                # Send SMS
                await self._send_sms(
                    to_number=sms_data['to_number'],
                    message=sms_data['message']
                )
                
                # Complete the message
                await msg.complete()
                
            except Exception as e:
                logger.error("SMS queue processing failed", error=e)
                await msg.abandon()
    
    async def _queue_notification(
        self,
        phone_number: str,
        notification_type: str,
        data: Dict[str, Any]
    ):
        """Queue notification for processing."""
        async with self.servicebus_client:
            sender = self.servicebus_client.get_queue_sender(
                queue_name=self.notification_queue
            )
            
            message = ServiceBusMessage(
                json.dumps({
                    "phone_number": phone_number,
                    "type": notification_type,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                })
            )
            
            await sender.send_messages(message)
    
    async def _send_sms(
        self,
        to_number: str,
        message: str
    ):
        """Send SMS using Twilio."""
        try:
            self.twilio_client.messages.create(
                to=to_number,
                from_=settings.TWILIO_PHONE_NUMBER,
                body=message
            )
        except TwilioRestException as e:
            logger.error("SMS send failed", error=e)
            raise
    
    def _format_outfit_response(self, analysis: Dict[str, Any]) -> str:
        """Format outfit analysis response for SMS."""
        items_text = "\n".join(
            f"- {item['description']}"
            for item in analysis.get('items', [])
        )
        
        return MessageTemplates.OUTFIT_ANALYSIS.format(
            response=analysis.get('response', ''),
            items=items_text,
            app_link="https://www.wha7.com"
        )

# Initialize service
async def get_message_service(
    ai_service: AIService = Depends(get_ai_service),
    image_service: ImageProcessingService = Depends(get_image_service)
) -> MessageService:
    """Get initialized message service."""
    return MessageService(
        ai_service=ai_service,
        image_service=image_service
    )