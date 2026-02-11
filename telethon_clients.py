#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telethon Clients - Alternative client implementation using Telethon
Lines: ~800
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path

# Telethon
from telethon import TelegramClient, events, functions, types
from telethon.errors import (
    FloodWaitError, SessionPasswordNeededError, 
    PhoneCodeInvalidError, PhoneCodeExpiredError,
    AuthKeyUnregisteredError, UsernameNotOccupiedError,
    PeerIdInvalidError, ChatAdminRequiredError,
    UserNotParticipantError, ChannelPrivateError
)
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.functions.channels import ReportSpamRequest
from telethon.tl.types import (
    InputChannel, InputUser, InputPeerChannel,
    InputPeerUser, InputReportReasonSpam,
    InputReportReasonViolence, InputReportReasonPornography,
    InputReportReasonChildAbuse, InputReportReasonOther,
    InputReportReasonCopyright, InputReportReasonPersonalDetails,
    InputReportReasonIllegalDrugs
)

# Local imports
from config_manager import get_config

logger = logging.getLogger(__name__)

class TelethonManager:
    """Manage Telethon clients for alternative reporting methods"""
    
    # Mapping of report reasons to Telethon types
    REPORT_REASONS = {
        "violence": InputReportReasonViolence(),
        "child_abuse": InputReportReasonChildAbuse(),
        "pornography": InputReportReasonPornography(),
        "illegal_drugs": InputReportReasonIllegalDrugs(),
        "personal_details": InputReportReasonPersonalDetails(),
        "spam": InputReportReasonSpam(),
        "copyright": InputReportReasonCopyright(),
        "other": InputReportReasonOther()
    }
    
    def __init__(self, config):
        self.config = config
        self.clients: Dict[str, TelegramClient] = {}
        self.sessions_path = Path("telethon_sessions")
        self.sessions_path.mkdir(exist_ok=True)
        
        logger.info("Telethon manager initialized")
    
    async def create_client(self, session_name: str, phone_number: str = None) -> TelegramClient:
        """Create a new Telethon client"""
        try:
            session_path = self.sessions_path / session_name
            
            client = TelegramClient(
                str(session_path),
                api_id=self.config.telegram.api_id,
                api_hash=self.config.telegram.api_hash,
                device_model=random.choice(self.config.anti_detection.device_models),
                app_version=random.choice(self.config.anti_detection.app_versions),
                system_version=random.choice(self.config.anti_detection.system_versions),
                lang_code="en",
                system_lang_code="en-US",
                flood_sleep_threshold=self.config.telegram.flood_sleep_threshold
            )
            
            await client.connect()
            
            if phone_number and not await client.is_user_authorized():
                # Not authorized, need to send code
                await client.send_code_request(phone_number)
            
            self.clients[session_name] = client
            logger.info(f"Created Telethon client: {session_name}")
            
            return client
            
        except Exception as e:
            logger.error(f"Failed to create Telethon client: {e}")
            raise
    
    async def get_client(self, session_name: str) -> Optional[TelegramClient]:
        """Get existing client or create new one"""
        if session_name in self.clients:
            client = self.clients[session_name]
            if client.is_connected():
                return client
            else:
                try:
                    await client.connect()
                    return client
                except:
                    pass
        
        return await self.create_client(session_name)
    
    async def sign_in(self, session_name: str, phone_number: str, 
                     code: str, phone_code_hash: str = None) -> Tuple[bool, str]:
        """Sign in with phone code"""
        try:
            client = await self.get_client(session_name)
            
            try:
                await client.sign_in(
                    phone=phone_number,
                    code=code,
                    phone_code_hash=phone_code_hash
                )
                
                # Get session string for backup
                session_string = client.session.save()
                
                logger.info(f"Successfully signed in: {phone_number}")
                return True, session_string
                
            except SessionPasswordNeededError:
                return False, "PASSWORD_NEEDED"
            except PhoneCodeInvalidError:
                return False, "کد نامعتبر است"
            except PhoneCodeExpiredError:
                return False, "کد منقضی شده است"
                
        except Exception as e:
            logger.error(f"Sign in failed: {e}")
            return False, f"خطا: {str(e)}"
    
    async def sign_in_with_password(self, session_name: str, password: str) -> Tuple[bool, str]:
        """Sign in with 2FA password"""
        try:
            client = await self.get_client(session_name)
            await client.sign_in(password=password)
            
            session_string = client.session.save()
            return True, session_string
            
        except Exception as e:
            logger.error(f"Password sign in failed: {e}")
            return False, f"خطا: {str(e)}"
    
    async def report_channel(self, client: TelegramClient, channel_id: Union[int, str], 
                            reason: str, message_id: int = None) -> bool:
        """Report a channel using Telethon"""
        try:
            # Get input entity
            if isinstance(channel_id, int):
                channel = await client.get_input_entity(channel_id)
            else:
                channel = await client.get_input_entity(channel_id)
            
            # Convert to InputChannel
            if isinstance(channel, types.InputPeerChannel):
                input_channel = InputChannel(
                    channel_id=channel.channel_id,
                    access_hash=channel.access_hash
                )
            else:
                # Try to get full channel
                full = await client.get_entity(channel_id)
                input_channel = InputChannel(
                    channel_id=full.id,
                    access_hash=full.access_hash
                )
            
            # Prepare report request
            report_reason = self.REPORT_REASONS.get(reason, InputReportReasonOther())
            
            if message_id:
                # Report specific message
                result = await client(ReportRequest(
                    peer=input_channel,
                    id=[message_id],
                    reason=report_reason
                ))
            else:
                # Report channel itself
                result = await client(functions.channels.ReportSpamRequest(
                    channel=input_channel,
                    user_id=None,
                    id=[]
                ))
            
            logger.info(f"Reported channel {channel_id} with reason: {reason}")
            return True
            
        except FloodWaitError as e:
            logger.warning(f"Flood wait for channel report: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return False
        except ChannelPrivateError:
            logger.debug(f"Channel {channel_id} is private")
            return False
        except Exception as e:
            logger.error(f"Failed to report channel {channel_id}: {e}")
            return False
    
    async def report_user(self, client: TelegramClient, user_id: Union[int, str],
                         reason: str) -> bool:
        """Report a user using Telethon"""
        try:
            # Get input entity
            if isinstance(user_id, int):
                user = await client.get_input_entity(user_id)
            else:
                user = await client.get_input_entity(user_id)
            
            # Convert to InputUser
            if isinstance(user, types.InputPeerUser):
                input_user = InputUser(
                    user_id=user.user_id,
                    access_hash=user.access_hash
                )
            else:
                # Try to get full user
                full = await client.get_entity(user_id)
                input_user = InputUser(
                    user_id=full.id,
                    access_hash=full.access_hash
                )
            
            # Report user
            report_reason = self.REPORT_REASONS.get(reason, InputReportReasonOther())
            
            result = await client(functions.users.ReportRequest(
                user_id=input_user,
                reason=report_reason
            ))
            
            logger.info(f"Reported user {user_id} with reason: {reason}")
            return True
            
        except FloodWaitError as e:
            logger.warning(f"Flood wait for user report: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return False
        except Exception as e:
            logger.error(f"Failed to report user {user_id}: {e}")
            return False
    
    async def report_message(self, client: TelegramClient, channel_id: Union[int, str],
                           message_id: int, reason: str) -> bool:
        """Report a specific message"""
        try:
            # Get input entity
            if isinstance(channel_id, int):
                channel = await client.get_input_entity(channel_id)
            else:
                channel = await client.get_input_entity(channel_id)
            
            # Convert to InputChannel
            if isinstance(channel, types.InputPeerChannel):
                input_channel = InputChannel(
                    channel_id=channel.channel_id,
                    access_hash=channel.access_hash
                )
            else:
                full = await client.get_entity(channel_id)
                input_channel = InputChannel(
                    channel_id=full.id,
                    access_hash=full.access_hash
                )
            
            # Report message
            report_reason = self.REPORT_REASONS.get(reason, InputReportReasonOther())
            
            result = await client(ReportRequest(
                peer=input_channel,
                id=[message_id],
                reason=report_reason
            ))
            
            logger.info(f"Reported message {message_id} in {channel_id}")
            return True
            
        except FloodWaitError as e:
            logger.warning(f"Flood wait for message report: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return False
        except Exception as e:
            logger.error(f"Failed to report message: {e}")
            return False
    
    async def get_dialog_info(self, client: TelegramClient, peer_id: Union[int, str]) -> Dict:
        """Get dialog information"""
        try:
            entity = await client.get_entity(peer_id)
            
            info = {
                "id": entity.id,
                "type": type(entity).__name__,
                "username": getattr(entity, "username", None),
                "title": getattr(entity, "title", None),
                "first_name": getattr(entity, "first_name", None),
                "last_name": getattr(entity, "last_name", None),
                "phone": getattr(entity, "phone", None),
                "access_hash": getattr(entity, "access_hash", None)
            }
            
            return info
            
        except UsernameNotOccupiedError:
            return {"error": "Username not occupied"}
        except PeerIdInvalidError:
            return {"error": "Invalid peer ID"}
        except Exception as e:
            logger.error(f"Failed to get dialog info: {e}")
            return {"error": str(e)}
    
    async def join_channel(self, client: TelegramClient, channel: Union[int, str]) -> bool:
        """Join a channel"""
        try:
            if isinstance(channel, str) and channel.startswith("@"):
                channel = channel[1:]
            
            await client.join_channel(channel)
            logger.info(f"Joined channel: {channel}")
            return True
            
        except FloodWaitError as e:
            logger.warning(f"Flood wait for join: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return False
        except Exception as e:
            logger.error(f"Failed to join channel {channel}: {e}")
            return False
    
    async def leave_channel(self, client: TelegramClient, channel: Union[int, str]) -> bool:
        """Leave a channel"""
        try:
            await client.leave_channel(channel)
            logger.info(f"Left channel: {channel}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to leave channel {channel}: {e}")
            return False
    
    async def get_recent_messages(self, client: TelegramClient, channel: Union[int, str],
                                limit: int = 5) -> List[Dict]:
        """Get recent messages from a channel"""
        try:
            messages = []
            async for message in client.iter_messages(channel, limit=limit):
                messages.append({
                    "id": message.id,
                    "date": message.date.isoformat() if message.date else None,
                    "message": message.text[:100] if message.text else None,
                    "sender_id": message.sender_id,
                    "views": message.views,
                    "forwards": message.forwards
                })
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get recent messages: {e}")
            return []
    
    async def send_view_action(self, client: TelegramClient, channel: Union[int, str],
                              message_id: int) -> bool:
        """Send view action to simulate reading"""
        try:
            # Get message to increment view counter
            await client.get_messages(channel, ids=message_id)
            return True
            
        except Exception as e:
            logger.debug(f"Failed to send view action: {e}")
            return False
    
    async def send_reaction(self, client: TelegramClient, channel: Union[int, str],
                           message_id: int, reaction: str = "👍") -> bool:
        """Send reaction to a message"""
        try:
            await client.send_reaction(channel, message_id, reaction)
            return True
            
        except Exception as e:
            logger.debug(f"Failed to send reaction: {e}")
            return False
    
    async def report_profile_photo(self, client: TelegramClient, user_id: Union[int, str],
                                  photo_id: int, reason: str = "spam") -> bool:
        """Report a profile photo"""
        try:
            # This requires specific API methods
            logger.warning("Profile photo reporting not implemented in Telethon")
            return False
            
        except Exception as e:
            logger.error(f"Failed to report profile photo: {e}")
            return False
    
    async def report_bot(self, client: TelegramClient, bot_username: str,
                        reason: str = "spam") -> bool:
        """Report a bot"""
        try:
            # Get bot entity
            bot = await client.get_entity(bot_username)
            
            # Report as user
            return await self.report_user(client, bot.id, reason)
            
        except Exception as e:
            logger.error(f"Failed to report bot: {e}")
            return False
    
    async def check_ban_status(self, client: TelegramClient) -> Dict:
        """Check if account is banned/limited"""
        try:
            # Try to get account info
            me = await client.get_me()
            
            # Try to send a message to Saved Messages
            await client.send_message("me", "Health check")
            
            return {
                "is_banned": False,
                "is_limited": False,
                "user_id": me.id,
                "username": me.username,
                "phone": me.phone
            }
            
        except FloodWaitError as e:
            return {
                "is_banned": False,
                "is_limited": True,
                "flood_wait": e.seconds
            }
        except Exception as e:
            return {
                "is_banned": True,
                "error": str(e)
            }
    
    async def export_session_string(self, session_name: str) -> Optional[str]:
        """Export session string for backup"""
        try:
            client = await self.get_client(session_name)
            return client.session.save()
        except Exception as e:
            logger.error(f"Failed to export session: {e}")
            return None
    
    async def import_session_string(self, session_name: str, session_string: str) -> bool:
        """Import session from string"""
        try:
            session_path = self.sessions_path / session_name
            client = TelegramClient(
                str(session_path),
                session=session_string,
                api_id=self.config.telegram.api_id,
                api_hash=self.config.telegram.api_hash
            )
            
            await client.connect()
            self.clients[session_name] = client
            
            logger.info(f"Imported session: {session_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import session: {e}")
            return False
    
    async def close_client(self, session_name: str):
        """Close a specific client"""
        try:
            if session_name in self.clients:
                client = self.clients[session_name]
                await client.disconnect()
                del self.clients[session_name]
                logger.info(f"Closed client: {session_name}")
        except Exception as e:
            logger.error(f"Failed to close client {session_name}: {e}")
    
    async def close_all(self):
        """Close all clients"""
        for session_name in list(self.clients.keys()):
            await self.close_client(session_name)
        logger.info("All Telethon clients closed")

# Utility functions for Telethon operations
def get_input_peer(entity) -> Optional[Union[InputPeerChannel, InputPeerUser]]:
    """Get input peer from entity"""
    try:
        if hasattr(entity, "access_hash"):
            if hasattr(entity, "channel_id"):
                return InputPeerChannel(
                    channel_id=entity.id,
                    access_hash=entity.access_hash
                )
            elif hasattr(entity, "user_id"):
                return InputPeerUser(
                    user_id=entity.id,
                    access_hash=entity.access_hash
                )
        return None
    except:
        return None

def extract_peer_id(entity) -> Optional[int]:
    """Extract peer ID from entity"""
    try:
        if hasattr(entity, "channel_id"):
            return entity.channel_id
        elif hasattr(entity, "user_id"):
            return entity.user_id
        else:
            return entity.id
    except:
        return None

async def wait_flood(fn, *args, **kwargs):
    """Wrapper for flood wait handling"""
    try:
        return await fn(*args, **kwargs)
    except FloodWaitError as e:
        logger.warning(f"Flood wait for {e.seconds}s")
        await asyncio.sleep(e.seconds + random.uniform(1, 5))
        return await fn(*args, **kwargs)

if __name__ == "__main__":
    # Test Telethon manager
    import asyncio
    
    async def test():
        from config_manager import get_config
        
        config = get_config()
        manager = TelethonManager(config)
        
        print(f"Telethon manager created")
        
        # Test client creation
        client = await manager.create_client("test_session")
        print(f"Client created: {client}")
        
        # Test getting me
        try:
            me = await client.get_me()
            print(f"Me: {me}")
        except:
            print("Not authorized")
        
        await manager.close_all()
    
    asyncio.run(test())