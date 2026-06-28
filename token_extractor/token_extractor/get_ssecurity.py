"""
Modified token_extractor to extract ssecurity after QR login.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import token_extractor as te

# Monkey-patch the login method to capture ssecurity
original_login = te.QrCodeXiaomiCloudConnector.login

def patched_login(self):
    result = original_login(self)
    if result:
        print(f"\n=== CREDENTIALS AFTER QR LOGIN ===")
        print(f"  _ssecurity: {getattr(self, '_ssecurity', 'NOT SET')}")
        print(f"  _serviceToken: {getattr(self, '_serviceToken', 'NOT SET')}")
        print(f"  userId: {getattr(self, 'userId', 'NOT SET')}")
        print(f"  _cUserId: {getattr(self, '_cUserId', 'NOT SET')}")
        print(f"  _psecurity: {getattr(self, '_psecurity', 'NOT SET')}")
        print(f"  _pass_token: {getattr(self, '_pass_token', 'NOT SET')}")
        
        # List all attributes
        attrs = [a for a in dir(self) if not a.startswith('__') and 'security' in a.lower() or 'token' in a.lower() or 'user' in a.lower() or 'service' in a.lower() or 'pass' in a.lower() or 'location' in a.lower() or 'cUser' in a.lower()]
        print(f"\n  All relevant attrs:")
        for a in attrs:
            if not callable(getattr(self, a, None)):
                print(f"    {a}: {getattr(self, a, 'N/A')}")
        
        # Try API call
        print(f"\n=== TRYING API CALL ===")
        try:
            url = self.get_api_url("cn") + "/v2/user/get_device_cnt"
            params = {"data": '{"fetch_own": true, "fetch_share": true}'}
            result = self.execute_api_call_encrypted(url, params)
            print(f"  get_device_cnt: {result}")
        except Exception as e:
            print(f"  API call error: {e}")
    return result

te.QrCodeXiaomiCloudConnector.login = patched_login

te.main()
