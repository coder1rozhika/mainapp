# Facebook Page Creator - Technical Reference
## Extracted from Meta Business Suite APK v547.0.0.40.109

### App Identity
- Package: `com.facebook.pages.app`
- Version: `547.0.0.40.109`
- Build: `922914753`
- API Key (Orca/Messenger, used for auth.login): `256002347743983`
- API Secret: `374e60f8b9bb6b8cbb30f78030438895`
- Business Suite App ID: `121876164619130`
- Business Suite Client Token: `1ab2c5c902faedd339c14b2d58e929dc`

### Other Known Facebook App IDs (from APK decompilation)
| App | Package | App ID |
|-----|---------|--------|
| Facebook Katana | com.facebook.katana | 350685531728 |
| Facebook Wakizashi | com.facebook.wakizashi | 350685531728 |
| Messenger (Orca) | com.facebook.orca | 256002347743983 |
| Business Suite (Pages) | com.facebook.pages.app | 121876164619130 |
| Facebook Lite | com.facebook.lite | 275254692598279 |
| Instagram | com.instagram.android | 567067343352427 |
| WhatsApp | com.whatsapp | 306069495113 |
| Threads | com.instagram.barcelona | 3419628305025917 |

### API Signature Computation
The `auth.login` endpoint uses `sig` instead of `access_token`:
```python
import hashlib
FB_API_SECRET = "374e60f8b9bb6b8cbb30f78030438895"

def fb_sig(params: dict) -> dict:
    params_str = "".join(f"{k}={v}" for k, v in sorted(params.items()))
    sig = hashlib.md5((params_str + FB_API_SECRET).encode("utf-8")).hexdigest()
    result = params.copy()
    result["sig"] = sig
    return result
```

### User-Agent
```
[FBAN/FBBusinessSuiteAndroid;FBAV/547.0.0.40.109;FBBV/922914753;FBDM/{density=2.0,width=1080,height=1920};FBLC/en_US;FBCR/;FBMF/Google;FBBD/google;FBPN/com.facebook.pages.app;FBDV/Pixel 4;FBSV/13.0;FBLR/0;FBBK/1;FBCA/arm64-v8a:;]
```

### Headers
```
Content-Type: application/x-www-form-urlencoded
X-FB-Connection-Type: WIFI
X-FB-HTTP-Engine: Liger
X-FB-Client-IP: True
X-FB-Server-Cluster: True
```

### Step 1: Login
```
POST https://b-api.facebook.com/method/auth.login

api_key=256002347743983
email=<uid>
password=<password>
credentials_type=password
generate_session_cookies=1
generate_machine_id=1
source=login
format=json
locale=en_US
client_country_code=US
fb_api_req_friendly_name=authenticate
fb_api_caller_class=com.facebook.auth.login.AuthenticationClient
method=auth.login
device_id=<uuid>
adid=<uuid>
meta_inf_fbmeta=
currently_logged_in_userid=0
try_num=1
sig=<computed via fb_sig()>
```
- Success: returns `access_token`, `uid`, `session_cookies`, `machine_id`
- 2FA needed: returns `error_code: 406`, `error_data` (JSON string with `machine_id`, `login_first_factor`, `uid`)
- IP blocked: returns `error_code: 1`, "An unknown error occurred"

### Step 2: 2FA
Same endpoint with modified params:
```
credentials_type=two_factor
password=<6-digit TOTP code>
twofactor_code=<6-digit TOTP code>
first_factor=<from step1 error_data.login_first_factor>
userid=<from step1 error_data.uid>
machine_id=<from step1 error_data.machine_id>
error_detail_type=button_with_disabled
sig=<recomputed via fb_sig()>
```
Note: `error_data` is a JSON string inside JSON - needs double parsing: `json.loads(response["error_data"])`

### Step 3: Create Page
```
POST https://graph.facebook.com/<uid>/accounts
name=<page_name>
category_enum=INTERNET_COMPANY
access_token=<from step2>
```

### Dependencies
```
pip install curl_cffi pyotp
```

### TOTP Generation
```python
import pyotp
code = pyotp.TOTP("WJNGTSBBDWFWUAXLMOZCYZ5MWLWT3664").now()
```

### Known Issues
- **Error 1 (IP blocking)**: Facebook blocks auth.login from datacenter/cloud IPs. Must run from residential or mobile network.
- **SSL Pinning**: The "patched" APK still has SSL certificate pinning active for Facebook domains.
