import plivo

from app.core.config import settings

class CallRecordService:
    def __init__(self):
        self.client = plivo.RestClient(
            settings.auth_id,
            settings.auth_token
        )

    def record_call(self, call_uuid: str):
        data = self.client.calls.record(
            call_uuid=call_uuid,
            time_limit=600
        )
        return {'call_uuid': call_uuid, 'url': data['url']}
    
    def stop_recording(self, call_uuid: str):
        self.client.calls.record_stop(
            call_uuid=call_uuid
        )
        return True

call_record_service = CallRecordService()