import plivo
from app.core.config import settings
from app.core import state

class CallRecordService:
    def __init__(self):
        # Prefer admin panel values if set, fallback to settings
        auth_id = state.admin_config.get("plivo_auth_id") or settings.auth_id
        auth_token = state.admin_config.get("plivo_auth_token") or settings.auth_token

        self.client = plivo.RestClient(auth_id, auth_token)

    def record_call(self, call_uuid: str):
        data = self.client.calls.record(
            call_uuid=call_uuid,
            time_limit=600
        )
        return {'call_uuid': call_uuid, 'url': data['url']}
    
    def stop_recording(self, call_uuid: str):
        self.client.calls.record_stop(call_uuid=call_uuid)
        return True

# Initialize service instance
call_record_service = CallRecordService()
