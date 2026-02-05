from fastapi import Response
import json

def trigger_toast(response: Response, message: str, level: str = "success"):
    trigger_data = {
        "show-toast": {
            "message": message,
            "level": level
        }
    }
    
    current_trigger = response.headers.get("HX-Trigger")
    if current_trigger:
        try:
            current_dict = json.loads(current_trigger)
            if isinstance(current_dict, dict):
                current_dict.update(trigger_data)
                response.headers["HX-Trigger"] = json.dumps(current_dict)
            else:
                response.headers["HX-Trigger"] = json.dumps(trigger_data)
        except:
            response.headers["HX-Trigger"] = json.dumps(trigger_data)
    else:
        response.headers["HX-Trigger"] = json.dumps(trigger_data)
