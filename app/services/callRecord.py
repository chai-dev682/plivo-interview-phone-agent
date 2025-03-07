import uuid
import plivo

from app.core.logger import logger
from app.core.config import settings

class CallRecordService:
    def __init__(self):
        self.client = plivo.RestClient(
            settings.auth_id,
            settings.auth_token
        )

    def record_call(self):
        response = self.client.calls.record(
            call_uuid=str(uuid.uuid4())
        )
        if response.status_code != 202:
            logger.error(f"Error recording call: {response.status_code} {response.error_code} {response.error_message}")
            return None
        else:
            data = response.json()
            return {'call_uuid': data['call_uuid'], 'url': data['url']}
    
    def stop_recording(self, call_uuid: str):
        response = self.client.calls.record_stop(
            call_uuid=call_uuid
        )
        if response.status_code != 204:
            logger.error(f"Error stopping recording: {response.status_code} {response.error_code} {response.error_message}")
            return False
        else:
            return True

call_record_service = CallRecordService()